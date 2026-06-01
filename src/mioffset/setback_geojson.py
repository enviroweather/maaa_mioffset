"""MI OFFset mapping with GeoJSON only

This is split from other mapping functions to minimize code needed
for cloud / web functions
"""

import numpy as np

##### import for type checking only
import typing as t
if t.TYPE_CHECKING:
    import numpy as np    
    
def fod_geojson(LL: np.ndarray, E: float, lat: float, lon: float) -> dict:
    """Create a GeoJSON FeatureCollection equivalent to fod_kml.

    Produces a point feature for the odor source and three polygon features
    for the 5%, 3%, and 1.5% setback footprints.

    Args:
        LL (np.ndarray): shape (81, 3, 2) array from fod_plot_to_ll where
            axis 0 = direction bins (80 + closing point),
            axis 1 = footprint level (0=5%, 1=3%, 2=1.5%),
            axis 2 = [longitude, latitude]
        E (float): Total Odor Emission Factor
        lat (float): latitude of the point source
        lon (float): longitude of the point source

    Returns:
        dict: GeoJSON FeatureCollection with four features (but not JSON str):
              one Point (source) and three Polygons (1.5%, 3%, 5% footprints)
    """
    def _ring(level_idx: int) -> list:
        # LL[d, p, 0] = lon, LL[d, p, 1] = lat — GeoJSON uses [lon, lat]
        return LL[:, level_idx, :].tolist()

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"name": "Odor source", "odor_emission_factor": E},
        },
        {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [_ring(2)]},
            "properties": {"name": "1.5% footprint", "level": "1.5%"},
        },
        {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [_ring(1)]},
            "properties": {"name": "3% footprint", "level": "3%"},
        },
        {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [_ring(0)]},
            "properties": {"name": "5% footprint", "level": "5%"},
        },
    ]

    return {"type": "FeatureCollection", "features": features}