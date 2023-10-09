# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
def classFactory(iface):  # pylint: disable=invalid-name
    from imodqgis.imod_plugin import ImodPlugin

    return ImodPlugin(iface)
