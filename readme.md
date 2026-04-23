# MI OFFSET : 2018-2026

**A tool for evaluating odor setback distance to minimize odor nuisance complaints.**

## *DEVELOPMENT AND TESTING VERSION 2026* 

Developed in cooperation with and sponsored by 

- [Michigan Alliance for Animal Agriculture (M-AAA)](https://www.canr.msu.edu/maaa/),  and 
- [Michigan Department of Agriculture and Rural Development (MDARD)](http://www.michigan.gov/mdard/)

![Circular odor footprint chart on a black background showing many white radial grid lines, a small gray center with irregular red and blue contour lines, and a larger green contour arc extending outward, illustrating modeled setback distances by wind direction.](doc/example_mioffset_plot.png)

MI OFFSET is a planning tool for assessing potential odor impacts from livestock facilities. 
output from this tool, called an odor footprint, is a radial plot which represents approximate distances 
that one must be away from the odor source to detect a noticeable or stronger odor up to 1.5%, 3% 
and 5% of the time for each of the 16 compass directions.  MI OFFSET 2018 is a revised version of 
the previous release of MI OFFSET (originally known as Michigan Odor Print) that improves its ability
to minimize odor nuisance risk when siting new or expanding livestock operations, through changes to the 
existing climatological dataset of wind and atmospheric stability.  

Technical details of the model are available in PDF format: [MIOFFSET2018_technicaldocument.pdf](doc/MIOFFSET2018_technicaldocument.pdf)

Documentation for installing and using the Python version of the model, see [src/mioffset/readme.md](src/mioffset/readme.md)

MI OFFSET 2018 has been implemented in the <a href='https://www.michigan.gov/mdard/0,4610,7-125-1599_1605---,00.html'>Site Selection Generally Accepted Agricultural and Management Practices (GAAMPs) document.</a> 

On 2/28/20, a revised version of MI OFFSET 2018 was released that includes a minor change to the underlying program to correct an error in the calculation of the wind direction climatology.  This revision should not affect most users.</p>

The project in this repository is work to modernize the code for 2025-2026, and 
it is still in development stage and not to be used.  For now, use the 2018 version 
available from the MSU Enviroweather project. 

<!-- MI OFFSET 2018 has been approved by MDARD for use in Michigan.  Users interested in siting 
guidance for farms outside of Michigan should refer to the regulations and/or guidelines in place in those states or 
provinces.  By using this product, you agree to the <a href="viewMioffsetTerms.php">Terms of Use</a>. -->

### Quick start

If you know how to use the command line and have python3 (min 3.11) installed, 
you can try installing this way (tested on Linux and MacOS)

1. copy this repository to your computer. 
2. strongly recommended to create and use virtual environmnet
    example with virtualenv in linux/MacOS shell (free open source env manager)

```shell
pip install virtualenv
virtualenv .venv
source .venv/bin/activate
```

3. in the main folder, run this
    `pip install --editable .`  

4. set up the .env file with settings for your AWS configuration

5. run the program for your latitude and longitue, and custom file name (to differentiate)
    `mioffset 43 -84 10 MIOFFSET_PY3`

6. check the output dir in the .env file you configured for graphs and map files


--- 

*All code and in this repository is (c) 2026 MSU Trustees and their
authors and not to be distributed without express permission*



