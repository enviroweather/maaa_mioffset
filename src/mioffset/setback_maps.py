# old mapping files

# vincenty method is deprecated, use geodesic method instead
import numpy as np
import simplekml
import shapefile
from mioffset.mioffset_utils import add_prefix_to_filename

##### import for type checking only
import typing as t
if t.TYPE_CHECKING:
    import numpy as np    
    
########## MAPPING ###########


def fod_kml(LL, E, lat, lon):
    """create KML formatted setback polygons for placing on a map

    Args:
        LL (np.ndarray): shape (81, 3, 2) array from fod_plot_to_ll where
            axis 0 = direction bins (80 + closing point),
            axis 1 = footprint level (0=5%, 1=3%, 2=1.5%),
            axis 2 = [longitude, latitude]
        E (float): Total Odor Emission Factor
        lat (float): latitude of the point source
        lon (float): longitude of the point source
        
    Returns:
        str: XML-formatted KML 
    """
    PLACE_MARK = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png' 

    kml = simplekml.Kml()
    pnt=kml.newpoint(name="", coords=[(lon,lat)])  # Source
    pnt.name = 'E=' +str(E)
    pnt.style.iconstyle.color = simplekml.Color.black
    pnt.style.iconstyle.scale = 1 
    pnt.style.iconstyle.icon.href = PLACE_MARK
    pol=kml.newpolygon(name="1.5% footprint",outerboundaryis=list(tuple(map(tuple,LL[:,2,:]))))
    pol.style.linestyle.color = simplekml.Color.green
    pol.style.linestyle.width = 10
    pol.style.polystyle.outline = 1
    pol.style.polystyle.fill = 0
    pol.visibility=0
    pol=kml.newpolygon(name="3% footprint",outerboundaryis=list(tuple(map(tuple,LL[:,1,:]))))
    pol.style.linestyle.color = simplekml.Color.blue
    pol.style.linestyle.width = 10
    pol.style.polystyle.outline = 1
    pol.style.polystyle.fill = 0
    pol.visibility=0
    pol=kml.newpolygon(name="5% footprint",outerboundaryis=list(tuple(map(tuple,LL[:,0,:]))))
    pol.style.linestyle.color = simplekml.Color.red
    pol.style.linestyle.width = 10
    pol.style.polystyle.outline = 1
    pol.style.polystyle.fill = 0
    return(kml)

    # string is kml.kml()
    
def write_kml(LL, E, lat, lon, kml_file_name):
    """create kml and save file from LL array 

    Args:
        LL (np array): set backs in lat/lon
        latval (float): point source latitude
        lonval (float): point source longitude
        kml_file_name (str): full path to kml file to save
    """
    
    kml = fod_kml(LL, E, lat, lon)     
    kml.save(kml_file_name)  


def kml_encode_base64(kml:str|simplekml.Kml, kml_file_name="kml"):
    """
    Convert KML content to a URL-safe Base64-encoded dictionary payload 
    (suitable for incorporation into JSON response)
    Accepts either a `simplekml.Kml` object or a raw KML XML string, encodes the
    KML content as UTF-8, then returns a dictionary where the key is the provided
    file name and the value is the Base64-encoded bytes.
    Args:
        kml (str | simplekml.Kml):
            KML content to encode. Must be either:
            - a `simplekml.Kml` instance (uses its `.kml()` output), or
            - a raw KML XML string.
        kml_file_name (str, optional):
            Key name to use in the returned dictionary. Defaults to `"kml"`.
    Returns:
        dict[str, bytes]:
            A dictionary containing one entry:
            `{kml_file_name: <urlsafe_base64_encoded_kml_bytes>}`.
    Raises:
        RuntimeError:
            If `kml` is neither a `simplekml.Kml`-like object (with `.kml()`) nor a string.
    """
    if hasattr(kml, 'kml'):
        kml_xml:str = kml.kml()   # type:ignore  # these methods do work
    elif isinstance(kml, str):
        kml_xml:str = kml        
    else:
        # don't know what this is
        raise RuntimeError("kml sent to kml2base64 is not a recognized type (kml or xml str)")
    kmlb64 = base64.urlsafe_b64encode(kml_xml.encode('utf-8'))
    kml_dict = {kml_file_name:kmlb64}
    return kml_dict


def kml_decode_base64(kml_dict: dict[str, bytes | str], kml_file_name: str = "kml") -> str:
    """Decode URL-safe Base64 KML payload back into XML text.

    Args:
        kml_dict (dict[str, bytes | str]):
            Dictionary payload containing one encoded KML value.
        kml_file_name (str, optional):
            Key name expected in kml_dict. Defaults to "kml".

    Returns:
        str: Decoded KML XML string.

    Raises:
        RuntimeError:
            If the payload is invalid or cannot be decoded as UTF-8 XML.
    """
    if not isinstance(kml_dict, dict):
        raise RuntimeError("kml_decode_base64 expects a dictionary payload")

    if kml_file_name not in kml_dict:
        raise RuntimeError(f"kml_decode_base64 missing key '{kml_file_name}' in payload")

    kmlb64 = kml_dict[kml_file_name]
    if isinstance(kmlb64, str):
        kmlb64_bytes = kmlb64.encode("ascii")
    elif isinstance(kmlb64, (bytes, bytearray)):
        kmlb64_bytes = bytes(kmlb64)
    else:
        raise RuntimeError("encoded KML value must be bytes or string")

    try:
        kml_xml_bytes = base64.urlsafe_b64decode(kmlb64_bytes)
        kml_xml = kml_xml_bytes.decode("utf-8")
    except Exception as exc:
        raise RuntimeError("failed to decode Base64 KML payload") from exc

    return kml_xml


        
def write_pointsource_shapefile(shapefile_name_stem:str, lonval:float, latval:float)->list[str]:
    """save single point shape file for mapping point source using pyshp
    https://github.com/GeospatialPython/pyshp?tab=readme-ov-file#writing-shapefiles
    
    SIDE EFFECT: files written to disk

    
    Args:
        shapefile_name_stem (str): base file name to use for components of shapefile
        lonval (float): longitude of point
        latval (float): latitude of point
    
    Returns:
        list[str]: list of all the actual files that were saved
    """
    w = shapefile.Writer(shapefile_name_stem, shapeType=shapefile.POINT)
    w.point(lonval,latval)
    w.field('Point')
    w.record('Odor_source')
    w.close()
    return([        
        f"{shapefile_name_stem}.dbf",
        f"{shapefile_name_stem}.shp",
        f"{shapefile_name_stem}.shx",                
    ])


def write_footprint_shapefile(shape_file_name_stem: str, LL: np.ndarray)->list[str]:
    """Write the footprint polygon shapefile and return list of 
    filenames created

    SIDE EFFECT: files written to disk
    
    Args:
        shape_file_name_stem (str): the 'stem' of the file, a full path with 
        a file name and no extension
        LL (np.ndarray): Lat Lon of footprint ring (usually the 5% one)

    Returns:
        list[str]: list of all the actual files that were saved
    """

    # uses pyshp
    # https://github.com/GeospatialPython/pyshp?tab=readme-ov-file#writing-shapefiles
        
    w = shapefile.Writer(shape_file_name_stem, shapeType=shapefile.POLYGON)
    w.poly([LL[:,0,:].tolist()])
    w.field('Polygon')
    w.record('5%_footprint')
    w.close()

    return [
        f"{shape_file_name_stem}.dbf",
        f"{shape_file_name_stem}.shp",
        f"{shape_file_name_stem}.shx",
    ]
