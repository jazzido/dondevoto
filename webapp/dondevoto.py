# coding: utf-8
from collections import OrderedDict
import simplejson

import dataset
import flask
from flask import Flask, render_template, jsonify, abort
from werkzeug import Request
from wsgiauth import basic

# Umbral para considerar válidas a los matches calculados por el algoritmo
MATCH_THRESHOLD = 0.95
DELETE_MATCHES_QUERY = """ DELETE
                           FROM weighted_matches
                           WHERE establecimiento_id = %d
                             AND escuela_id = %d
                             AND match_source = 1 """

class MethodRewriteMiddleware(object):
    def __init__(self, app, input_name='_method'):
        self.app = app
        self.input_name = input_name

    def __call__(self, environ, start_response):
        request = Request(environ)
        if self.input_name in request.form:
            method = request.form[self.input_name].upper()

            if method in ['GET', 'POST', 'PUT', 'DELETE']:
                environ['REQUEST_METHOD'] = method

        return self.app(environ, start_response)

def authfunc(env, username, password):
    # TODO guardar username en env, para guardar el autor de los matches
    return password == 'dondevoto'

app = Flask(__name__)
app.wsgi_app = basic.basic('dondevoto', authfunc)(MethodRewriteMiddleware(app.wsgi_app))

db = dataset.connect('postgresql://manuel@localhost:5432/mapa_paso')

def provincias_distritos():
    """ mapa distrito -> [seccion, ..., seccion] """

    rv = OrderedDict()
    q = """
            SELECT da.dne_distrito_id,
                   da.provincia,
                   da.dne_seccion_id,
                   da.departamento,
                   count(e.*) AS estab_count,
                   count(wm.*) AS matches_count
            FROM divisiones_administrativas da
            INNER JOIN establecimientos e
               ON e.dne_distrito_id = da.dne_distrito_id
               AND e.dne_seccion_id = da.dne_seccion_id
            LEFT OUTER JOIN weighted_matches wm
               ON wm.establecimiento_id = e.id AND wm.score = 1
            GROUP BY da.dne_distrito_id,
                     da.provincia,
                     da.dne_seccion_id,
                     da.departamento
            ORDER BY provincia,
                     departamento
        """
    for d in db.query(q):
        k = (d['dne_distrito_id'], d['provincia'],)
        if k not in rv:
            rv[k] = []
        rv[k].append((d['dne_seccion_id'],
                      d['departamento'],
                      d['estab_count'],
                      d['matches_count']))

    return rv

@app.route("/")
def index():
    return render_template('index.html',
                           provincias_distritos=provincias_distritos())

@app.route("/completion")
def completion():
    q = """ SELECT da.provincia,
                   count(e.*) AS estab_count,
                   count(wm.*) AS matches_count
            FROM divisiones_administrativas da
            INNER JOIN establecimientos e
               ON e.dne_distrito_id = da.dne_distrito_id
               AND e.dne_seccion_id = da.dne_seccion_id
            LEFT OUTER JOIN weighted_matches wm
               ON wm.establecimiento_id = e.id AND wm.score >= 0.95
            GROUP BY da.provincia
            ORDER BY provincia """

    return flask.Response(flask.json.dumps(list(db.query(q))),
                          mimetype='application/json')

@app.route("/seccion/<int:distrito_id>/<int:seccion_id>")
def seccion_info(distrito_id, seccion_id):
    q = """ SELECT *,
                   st_asgeojson(st_setsrid(wkb_geometry, 900913)) AS geojson,
                   st_asgeojson(st_envelope(wkb_geometry)) AS bounds
            FROM divisiones_administrativas
            WHERE dne_distrito_id = %d
              AND dne_seccion_id = %d """ % (distrito_id, seccion_id)

    r = [dict(e.items() + [('geojson',simplejson.loads(e['geojson'])),('wkb_geometry', ''), ('bounds',simplejson.loads(e['bounds']))])
         for e in db.query(q)][0]

    return flask.Response(flask.json.dumps(r),
                          mimetype='application/json')


@app.route("/establecimientos/<int:distrito_id>/<int:seccion_id>")
def establecimientos_by_distrito_and_seccion(distrito_id, seccion_id):
    q = """ SELECT e.id, e.establecimiento, e.direccion, e.localidad, e.circuito, count(wm.*) AS match_count
            FROM establecimientos e
            LEFT OUTER JOIN weighted_matches wm
               ON wm.establecimiento_id = e.id AND wm.score > 0.95
            WHERE dne_distrito_id = %d
              AND dne_seccion_id = %d
            GROUP BY e.id, e.establecimiento, e.direccion, e.localidad, e.circuito """ % (distrito_id, seccion_id)

    return flask.Response(flask.json.dumps(list(db.query(q))),
                          mimetype='application/json')



@app.route("/matches/<int:establecimiento_id>", methods=['GET'])
def matched_escuelas(establecimiento_id):
    """ obtener los matches para un establecimiento """

    q = """
       SELECT wm.score,
       wm.establecimiento_id,
       esc.*,
       st_asgeojson(wkb_geometry_4326) AS geojson,
       (CASE WHEN wm.match_source = 1 THEN 1
             WHEN wm.score > %f AND wm.match_source = 0 THEN 1
             ELSE 0
        END) AS is_match
       FROM weighted_matches wm
       INNER JOIN establecimientos e ON e.id = wm.establecimiento_id
       INNER JOIN escuelasutf8 esc ON esc.ogc_fid = wm.escuela_id
       WHERE wm.establecimiento_id = %d
         AND esc.estado = 'Activo'
       ORDER BY wm.score DESC
       """ % (MATCH_THRESHOLD, establecimiento_id)

    r = [dict(e.items() + [('geojson',simplejson.loads(e['geojson']))])
         for e in db.query(q)]

    return flask.Response(flask.json.dumps(r),
                          mimetype='application/json')

@app.route("/places/<int:distrito_id>/<int:seccion_id>")
def places_for_distrito_and_seccion(distrito_id, seccion_id):
    """ Todos los places (escuelas) para este distrito y seccion """
    q = """ SELECT esc.*
            FROM escuelasutf8 esc
            WHERE esc.dne_distrito_id = %d
              AND esc.dne_seccion_id = %d """

    return flask.Response(flask.json.dumps(list(db.query(q))),
                          mimetype='application/json')

@app.route('/matches/<int:establecimiento_id>/<int:place_id>',
           methods=['DELETE'])
def match_delete(establecimiento_id, place_id):
    """ modificar los weighted_matches para un (establecimiento, escuela) """
    # borrar todos los matches humanos anteriores
    q = DELETE_MATCHES_QUERY % (establecimiento_id, place_id)
    db.query(q)
    return flask.Response('')


@app.route('/matches/<int:establecimiento_id>/<int:place_id>', methods=['POST'])
def match_create(establecimiento_id, place_id):
    # asegurarse que el establecimiento y el lugar existan
    # y que el lugar este contenido dentro de la region geografica
    # del establecimiento
    q = """ SELECT e.*,
                   esc.*
            FROM establecimientos e
            INNER JOIN divisiones_administrativas da ON e.dne_distrito_id = da.dne_distrito_id
            AND e.dne_seccion_id = da.dne_seccion_id
            INNER JOIN escuelasutf8 esc ON st_within(esc.wkb_geometry_4326, da.wkb_geometry)
            WHERE e.id = %d
              AND esc.ogc_fid = %d """ % (establecimiento_id, place_id)

    if len(list(db.query(q))) == 0:
        abort(400)

    # crear un match para un (establecimiento, escuela) implica
    # borrar todos los matches humanos anteriores
    q = DELETE_MATCHES_QUERY % (establecimiento_id, place_id)
    db.query(q)

    db['weighted_matches'].insert({
        'establecimiento_id': establecimiento_id,
        'escuela_id': place_id,
        'score': 1,
        'match_source': 1 # human
    })

    return flask.Response('')
