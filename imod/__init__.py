def classFactory(iface):  # pylint: disable=invalid-name
    from .imod_plugin import ImodPlugin
    return ImodPlugin(iface)
