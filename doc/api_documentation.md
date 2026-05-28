## MI Offset Cloud API Response Structure

This is an outline of what the response looks like to work with it.   
The structure is likely to change as we develop this system. 

 The code to build this response is in this repo in `src/mioffset/mioffset.py`

A JSON schema file is in this repo in [/doc/response_schema.json](./response_schema.json)

A summary of the structure is as follows.  It has top level sections, 

- meta = information about the API or the call
- inputs = repeat of the input parameters used
- response  = dictionary of different kinds of input.  Currently one entry per dictionary key but that may change 
  as we accommodate providing subsets of the season (MI Offset legacy can show results just using warm season wind)  
  

Response keys: 


- "raw" : the array of data output by the FOD model `
- "table" : a formatted version of the raw data left over from legacy site.  May not be needed
- "map" : a spatial feature file of the offset model for placement on a map.  
        currently uses widely usedGeoJSON format.  Legacy used KML and Shapefile formats which are not 
        web friendly
- "plot" : A polar plot of the offset model output.   does not have spatial info so can't be put on a map
        this was displayed by legacy in output, mimicing the original Excel spreadsheet from 2000
        neigther of which had mapping capability at the time.  Could be place below the table in the output

Each sub-dictionary has two keys, 

1. "format" which is the mimetype of the data, not that useful now 
but doing that for full transparency for future applications
2. "data" 

python code snippet that generates the output (currently).  

```
     fod_response["meta"] = {
        "version" : str(version),   # version of package
        "timestamp" : datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    fod_response["inputs"] = {
        "lat":lat, 
        "lon":lon, 
        "oef":odor_index 
    }
    
    fod_response["outputs"] = {
        "raw" : {"format": "application/json",  "data": fod_results },
        "table" : {"format": "text/plain", "data": table_text },
        "map" : {"format" : "application/geo+json", "data" : geo_json },
        "plot" : {"format" : "image/svg+xml;charset=utf-8", "data": plot_svg }                           
    }
                        
```