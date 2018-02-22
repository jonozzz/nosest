'''
Created on Apr 7, 2016

@author: jono
'''
from .scaffolding import Stamp
import logging
from ...base import AttrDict
from f5test.utils.parsers.tmsh import RawEOL
# from ...base import enum
# from ...utils.parsers import tmsh
# from ...utils.parsers.tmsh import RawEOL

LOG = logging.getLogger(__name__)


class GbbpDG(Stamp):
    TMSH = """
    ltm rule %(key)s [BEGIN]
        when HTTP_REQUEST {
    
      # Save the host header value set to lowercase
      set host [string tolower [getfield [HTTP::host] ":" 1]]
      log local0.debug $host
       # Check the host header value
      switch -glob $host {
          "*.sharepoint.com" {
              # Remove the -admin., -my., -web., - token from the hostname
              set var [getfield $host "." 1]
              if {[string index $var end-14] == "-" && [string is xdigit [string range $var end-13 end]]} {
                  set host [string replace $var end-13 end "app.[domain $host 2]"]}
                 set host [string map {-admin. . -my. . -web. . -app. . -public. .} $host]
             }
          "www.*" {
              # Remove www. token from the hostname
              set host [getfield $host "www." 2]
             }
          "*sharepoint.microsoftonline.com" {
              # Get the tenant prefix from the hostname
              set host "[getfield $host "-" 1].sharepoint.microsoftonline.com"
             }
          "*sharepoint.emea.microsoftonline.com" {
             # Get the tenant prefix from the hostname
             set host "[getfield $host "-" 1].sharepoint.emea.microsoftonline.com"
             }
          "*sharepoint.apac.microsoftonline.com" {
            # Get the tenant prefix from the hostname
            set host "[getfield $host "-" 1].sharepoint.apac.microsoftonline.com"
             }
        }
      # Look up the parsed hostname in the datagroup
      set destpool [class match -value $host equals datagroup_1m]
    
      # Check if there was a match in the datagroup
      if { $destpool ne "" } {
    
         # Check if port was 80 or not
         if { [TCP::local_port] == 80 } {
             set isSSL "False"
             set SSLOn "Off"
         } else {
             set isSSL "True"
             set SSLOn "On"
         }
    
         # Remove all existing header instances for this name
         HTTP::header remove "X-SPO-SSL-Connection"
    
         # Insert a new header with the $isSSL flag set to true or false
         HTTP::header insert "X-SPO-SSL-Connection" "$isSSL"
    
         HTTP::header remove "Front-End-Https"
         HTTP::header insert "Front-End-Https" "$SSLOn"
    
         # use sp pool1
        log local0.debug  "%(snatpool1)s"
            snatpool "%(snatpool1)s"
    
      }
      else {
      # use sp pool2
      log local0.debug "%(snatpool2)s"
      snatpool "%(snatpool2)s"
      }
     }
    [END]
    """

    def __init__(self, name='snat_pool_selection-data-group-1M', snatpool1=None,
                 snatpool2=None):
        self.name = name
        self.snatpool1 = snatpool1 or AttrDict(name='')
        self.snatpool2 = snatpool2  or AttrDict(name='')
        super(GbbpDG, self).__init__()

    def tmsh(self, obj):
        key = self.get_full_path()
        # partition = self.folder.partition().name
        value = obj.format(key=key, snatpool1=self.snatpool1.name,
                           snatpool2=self.snatpool1.name)
        return key, value


class LargeAppRule(Stamp):
    TMSH = r"""
    ltm rule %(key)s {
        when HTTP_REQUEST {
            if { [HTTP::uri] contains "large" }  {
                 CLASSIFY::application set %(app_name)s
            }
        }
    }

    ltm classification application %(app_name)s {
        application-id 8193
        category %(folder)s/Video
        description "Large HTML file Sizes"
    }
    """

    def __init__(self, name=None, app_name=None):
        self.name = name
        self.app_name = app_name
        super(LargeAppRule, self).__init__()

    def tmsh(self, obj):
        key = self.get_full_path()
        # partition = self.folder.partition().name
        app_name = self.folder.SEPARATOR.join((self.folder.key(), self.app_name))
        value = obj.format(key=key, app_name=app_name,
                           folder=self.folder.key())
        return key, value

    def reference(self):
        key = self.folder.SEPARATOR.join((self.folder.key(), self.name))
        return {key: RawEOL}
