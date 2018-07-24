'''
Created on Mar 16, 2013

@author: jono
'''
import io
import logging
import os
import sys

try:
    import yaml
except ImportError:
    raise Exception('unable to import YAML package. Can not continue.')

from ...base import AttrDict
from ...utils.dicts import merge
from ...utils.net import get_local_ip


LOG = logging.getLogger(__name__)
CONFIG = AttrDict()
EXTENDS_KEYWORD = '$extends'
PEER_IP = '224.0.0.1'


class Signals(object):
    from blinker import Signal
    on_before_load = Signal()
    on_before_extend = Signal()
    on_after_extend = Signal()


class YamlLoader(yaml.Loader):
    """
    yaml.Loader subclass handles "!include path/to/foo.yml" directives in config
    files.  When constructed with a file object, the root path for includes
    defaults to the directory containing the file, otherwise to the current
    working directory. In either case, the root path can be overridden by the
    `root` keyword argument.

    When an included file F contain its own !include directive, the path is
    relative to F's location.

    Example:
        YAML file /home/frodo/one-ring.yml:
            ---
            Name: The One Ring
            Specials:
                - resize-to-wearer
            Effects:
                - !include path/to/invisibility.yml

        YAML file /home/frodo/path/to/invisibility.yml:
            ---
            Name: invisibility
            Message: Suddenly you disappear!

        Loading:
            data = IncludeLoader(open('/home/frodo/one-ring.yml', 'r')).get_data()

        Result:
            {'Effects': [{'Message': 'Suddenly you disappear!', 'Name':
                'invisibility'}], 'Name': 'The One Ring', 'Specials':
                ['resize-to-wearer']}
    """
    def __init__(self, *args, **kwargs):
        super(YamlLoader, self).__init__(*args, **kwargs)
        self.add_constructor('!include', self._include)
        self.add_constructor('!append', self._append)
        if 'root' in kwargs:
            self.root = kwargs['root']
        elif isinstance(self.stream, io.IOBase):
            self.root = os.path.dirname(self.stream.name)
        else:
            self.root = os.path.curdir

    def _load_node(self, node):
        filename = os.path.join(self.root, self.construct_scalar(node))
        f = open(filename, 'r')
        loader = yaml.Loader(f)
        subnode = loader.get_single_node()
        return subnode

    def flatten_mapping(self, node):
        merge = []
        index = 0
        while index < len(node.value):
            key_node, value_node = node.value[index]
            if key_node.tag == 'tag:yaml.org,2002:merge':
                del node.value[index]
                if isinstance(value_node, yaml.MappingNode):
                    self.flatten_mapping(value_node)
                    merge.extend(value_node.value)
                elif isinstance(value_node, yaml.SequenceNode):
                    submerge = []
                    for subnode in value_node.value:
                        if not isinstance(subnode, yaml.MappingNode):
#                             raise yaml.constructor.ConstructorError("while constructing a mapping",
#                                     node.start_mark,
#                                     "expected a mapping for merging, but found %s"
#                                     % subnode.id, subnode.start_mark)
                            subnode = self._load_node(subnode)
                        self.flatten_mapping(subnode)
                        submerge.append(subnode.value)
                    submerge.reverse()
                    for value in submerge:
                        merge.extend(value)
                else:
                    # raise yaml.constructor.ConstructorError("while constructing a mapping", node.start_mark,
                    #        "expected a mapping or list of mappings for merging, but found %s"
                    #        % value_node.id, value_node.start_mark)
                    value_node = self._load_node(value_node)
                    self.flatten_mapping(value_node)
                    merge.extend(value_node.value)
            elif key_node.tag == 'tag:yaml.org,2002:value':
                key_node.tag = 'tag:yaml.org,2002:str'
                index += 1
            else:
                index += 1
        if merge:
            node.value = merge + node.value

    def _include(self, loader, node):
        oldRoot = self.root
        filename = os.path.join(self.root, loader.construct_scalar(node))
        self.root = os.path.dirname(filename)
        data = yaml.load(open(filename, 'r'))
        self.root = oldRoot
        return data

    def _append(self, loader, node):
        # value = loader.construct_scalar(node)
        value = loader.construct_yaml_int(node)
        return lambda x: x.append(value)
        # return lambda x: x.append(node)

    def _construct_mapping(self, node, deep=False):
        if not isinstance(node, yaml.MappingNode):
            raise yaml.constructor.ConstructorError(None, None,
                    "expected a mapping node, but found %s" % node.id,
                    node.start_mark)
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                hash(key)
            except TypeError as exc:
                raise yaml.constructor.ConstructorError("while constructing a mapping", node.start_mark,
                        "found unacceptable key (%s)" % exc, key_node.start_mark)
            value = self.construct_object(value_node, deep=deep)
            if key in mapping:
                # print mapping, key, value
                if callable(value):
                    value(mapping[key])
                    continue
            mapping[key] = value
        return mapping

    def construct_mapping(self, node, deep=False):
        if isinstance(node, yaml.MappingNode):
            self.flatten_mapping(node)
        return self._construct_mapping(node, deep=deep)


class ConfigLoader(object):

    def __init__(self, filename, fmt=None):
        self.loaders = {'yaml': self.load_yaml,
                        'json': self.load_json,
                        'ini': self.load_ini,
                        'py': self.load_python}
        self.filename = filename
        self.fmt = fmt

    def load(self):
        # Load the configuration file:
        Signals.on_before_load.send(self, filename=self.filename)
        main_config = self.load_any(self.filename)

        config_dir = os.path.dirname(self.filename)
        Signals.on_before_extend.send(self, config=main_config)
        config = self.extend(config_dir, main_config)
        # Substitute {0[..]} tokens. Works only with strings.
        self.subst_variables(config)

        config = AttrDict(config)
        config['_filename'] = self.filename
        config['_argv'] = ' '.join(sys.argv)
        config['_cwd'] = os.getcwd()
        config['_local_ip'] = get_local_ip(PEER_IP)

        Signals.on_after_extend.send(self, config=config)
        return config

    def extend(self, cwd, config, extra=None):
        bases = config.get(EXTENDS_KEYWORD) or []
        if bases and isinstance(bases, str):
            bases = [bases]

        if extra and isinstance(extra, str):
            extra = [extra]
        else:
            extra = []

        assert isinstance(bases, list), 'Expected a list of files in %s' % EXTENDS_KEYWORD
        bases += extra

        for filename in reversed(bases):
            filename = os.path.join(cwd, filename)
            base_config = self.extend(os.path.dirname(filename),
                                      self.load_any(filename))
            config = merge(base_config, config)
        return config

    def subst_variables(self, src, root=None):
        if not root:
            root = src

        def _subst(hashable, key):
            return
# With ansible's flexibility I don't think we'll need this var substitution feature
#             try:
#                 if isinstance(hashable[key], basestring):
#                     hashable[key] = hashable[key].format(CFG=root, ENV=os.environ)
#             except (KeyError, ValueError):
#                 LOG.debug('Key %s cannot be formatted.', v)

        if isinstance(src, dict):
            for k, v in src.items():
                if isinstance(v, dict):
                    self.subst_variables(v, root)
                elif isinstance(v, str):
                    _subst(src, k)
                elif isinstance(v, (list, tuple)):
                    for i in range(len(v)):
                        if isinstance(v[i], dict):
                            self.subst_variables(v[i], root)
                        else:
                            _subst(v, i)

    def load_any(self, filename):
        fmt = self.fmt or os.path.splitext(filename)[1][1:]
        assert fmt in self.loaders, 'Unknown format: %s' % fmt
        return self.loaders[fmt](filename)

    @staticmethod
    def load_yaml(filename):
        """ Load the passed in yaml configuration file """
        with open(filename, 'r') as f:
            return yaml.load(f, YamlLoader)
            # return yaml.load(open(filename).read(), YamlLoader)

    @staticmethod
    def load_ini(filename):
        """ Parse and collapse a ConfigParser-Style ini file into a nested,
        eval'ing the individual values, as they are assumed to be valid
        python statement formatted """
        import configparser
        tmpconfig = configparser.ConfigParser()
        tmpconfig.read(filename)
        config = {}
        for section in tmpconfig.sections():
            config[section] = {}
            for option in tmpconfig.options(section):
                config[section][option] = tmpconfig.get(section, option)
        return config

    @staticmethod
    def load_python(filename):
        """ This will eval the defined python file into the config variable -
        the implicit assumption is that the python is safe, well formed and will
        not do anything bad. This is also dangerous. """
        return eval(open(filename, 'r').read())

    @staticmethod
    def load_json(filename):
        import json
        return json.load(open(filename))
