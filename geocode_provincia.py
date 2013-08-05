# coding: utf-8
import re
import sys

import dataset
from geopy.geocoders.googlev3 import GoogleV3

POINT_RE = r'^POINT\((-?[\d\.]+) (-?[\d\.]+)\)$'

db = dataset.connect('postgresql://manuel@localhost:5432/mapa_paso')

def geocode_establecimiento(establecimiento, max_distance=20, ciudad=None):
    """ recibe un establecimiento (dict)
        geocodea via Google
        busca las escuela más cercanas y "más parecidas" por nombre
    """

    geocoder = GoogleV3()

    print >>sys.stderr, "Geocoding: %s (%s)" % (establecimiento['establecimiento'], establecimiento['localidad'])

    # bounds del distrito, para biasear al geocoder
    q = """
        SELECT st_astext(st_pointn(st_boundary(st_envelope(g.wkb_geometry)),1)) AS sw,
               st_astext(st_pointn(st_boundary(st_envelope(g.wkb_geometry)),3)) AS ne
        FROM
          (SELECT wkb_geometry
           FROM divisiones_administrativas da
           WHERE dne_distrito_id = %d
             AND dne_seccion_id = %d) g
        """ % (establecimiento['dne_distrito_id'], establecimiento['dne_seccion_id'])
    bounds = db.query(q).next()
    bounds['sw'] = re.match(POINT_RE, bounds['sw']).groups()
    bounds['ne'] = re.match(POINT_RE, bounds['ne']).groups()

    try:
        geocoded = geocoder.geocode("%s, %s, Argentina" % (establecimiento['direccion'],
                                                           ciudad if ciudad is not None else establecimiento['localidad']),
                                    bounds="%s,%s|%s,%s" % (bounds['sw'][1], bounds['sw'][0],bounds['ne'][1], bounds['ne'][0]),
                                    exactly_one=True,
                                    region='ar')
    except:
        print >>sys.stderr, "EXECPTION: %s" % sys.exc_info()[0]
        return None

    # escuelas cerca del resultado geocodeado, cuyo nombre se parece al establecimiento de votacion
    q = """ SELECT *,
            st_distance(st_geographyfromtext('SRID=4326;' || st_astext(wkb_geometry_4326)),
                        st_geographyfromtext('SRID=4326;POINT(%s %s)')) AS dist
            FROM escuelasutf8
            WHERE st_within(wkb_geometry_4326,
                            (SELECT st_collect(da.wkb_geometry) AS geom
                             FROM divisiones_administrativas da
                             WHERE da.dne_seccion_id = %s
                               AND da.dne_distrito_id = %s))
              AND st_distance(st_geographyfromtext('SRID=4326;' || st_astext(wkb_geometry_4326)),
                              st_geographyfromtext('SRID=4326;POINT(%s %s)')) <= %f
              AND similarity(nombre, '%s') > 0.5
        """ % (geocoded[1][1],
               geocoded[1][0],
               establecimiento['dne_seccion_id'],
               establecimiento['dne_distrito_id'],
               geocoded[1][1],
               geocoded[1][0],
               max_distance,
               establecimiento['establecimiento'].replace("'","''"))

    r = db.query(q)
    if r.count == 0:
        return None

    return (establecimiento['id'], r.next()['ogc_fid'],)

if __name__ == '__main__':
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print >>sys.stderr, "Usage: %s dne_distrito_id dne_seccion_id [ciudad]"
        sys.exit(-1)

    ciudad = sys.argv[3] if len(sys.argv) == 4 else None
    q = "SELECT * FROM establecimientos WHERE dne_distrito_id = %s AND dne_seccion_id = %s" % tuple(sys.argv[1:3])
    for est in db.query(q):
        r = geocode_establecimiento(est, ciudad=ciudad)
        if r is not None:
            print "%s,%s" % r
