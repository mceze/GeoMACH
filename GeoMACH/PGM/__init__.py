# sphinx autodoc complains if PGMlib doesn't exist when the docs are built,
# so wrap a try block around the import so we can still get autogenerated
# source docs
# from GeoMACH.PGM.core import *
# try:
import GeoMACH.PGM.PGMlib as PGMlib
# except ImportError:
#     PGMlib = None
