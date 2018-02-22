from .base import EMCommand

discover = None
class Discover(EMCommand):
    """Discover devices by specific addresses."""
    
    def __init__(self, specs, *args, **kwargs):
        super(Discover, self).__init__(*args, **kwargs)
        
        self.specs = specs

    def setup(self):
        em = self.api
        return int(em.discovery.discoverByAddress('', '', self.specs)['uid'])


delete = None
class Delete(EMCommand):
    """Delete devices by uids."""
    
    def __init__(self, uids, *args, **kwargs):
        super(Delete, self).__init__(*args, **kwargs)
        self.uids = uids

    def setup(self):
        em = self.api
        return em.device.delete_device(self.uids)


set_config = None
class SetConfig(EMCommand):
    """Set default EM configuration."""
    
    def __init__(self, auto_refresh=False, *args, **kwargs):
        super(SetConfig, self).__init__(*args, **kwargs)
        self.auto_refresh = auto_refresh

    def setup(self):
        em = self.api
        auto_refresh = str(self.auto_refresh).lower()
        return em.device.setDeviceConfig(60, 'include', 
                                         'http://devcentral.f5.com', auto_refresh)

