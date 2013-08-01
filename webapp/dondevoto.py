from collections import OrderedDict
import simplejson

import dataset
import flask
from flask import Flask, render_template, jsonify
from werkzeug import Request

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

app = Flask(__name__)
app.wsgi_app = MethodRewriteMiddleware(app.wsgi_app)

db = dataset.connect('postgresql://manuel@localhost:5432/mapa_paso')

def provincias_distritos():
    """ mapa distrito -> [seccion, ..., seccion] """

    rv = OrderedDict()
    for d in db.query(""" select da.dne_distrito_id, da.provincia, da.dne_seccion_id, da.departamento, count(e.*) as estab_count from divisiones_administrativas da
                          inner join establecimientos e
                          on e.dne_distrito_id = da.dne_distrito_id and e.dne_seccion_id = da.dne_seccion_id
                          group by da.dne_distrito_id, da.provincia, da.dne_seccion_id, da.departamento
                          order by provincia, departamento """):
        k = (d['dne_distrito_id'], d['provincia'],)
        if k not in rv:
            rv[k] = []
        rv[k].append((d['dne_seccion_id'], d['departamento'], d['estab_count']))

    return rv

@app.route("/")
def index():
    return render_template('index.html',
                           provincias_distritos=provincias_distritos())

@app.route("/seccion/<int:distrito_id>/<int:seccion_id>")
def seccion_info(distrito_id, seccion_id):
    q = """ select *, st_asgeojson(st_setsrid(wkb_geometry, 900913)) as geojson, st_asgeojson(st_envelope(wkb_geometry)) as bounds
            from divisiones_administrativas
            where dne_distrito_id = %d and dne_seccion_id = %d """ % (distrito_id, seccion_id)

    r = [dict(e.items() + [('geojson',simplejson.loads(e['geojson'])),('wkb_geometry', ''), ('bounds',simplejson.loads(e['bounds']))])
         for e in db.query(q)][0]

    return flask.Response(flask.json.dumps(r),
                          mimetype='application/json')


@app.route("/establecimientos/<int:distrito_id>/<int:seccion_id>")
def establecimientos_by_distrito_and_seccion(distrito_id, seccion_id):
    q = """ select * from establecimientos
            where dne_distrito_id = %d and dne_seccion_id = %d """ % (distrito_id, seccion_id)

    return flask.Response(flask.json.dumps(list(db.query(q))),
                          mimetype='application/json')

@app.route("/matches/<int:establecimiento_id>", methods=['GET'])
def matched_escuelas(establecimiento_id):
    """ obtener los matches para un establecimiento """

    q = """ select wm.score, wm.establecimiento_id, esc.*, st_asgeojson(wkb_geometry_4326) as geojson
            from weighted_matches wm
            inner join establecimientos e on e.id = wm.establecimiento_id
            inner join escuelasutf8 esc on esc.ogc_fid = wm.escuela_id
            where wm.establecimiento_id = %d and esc.estado = 'Activo'
            order by wm.score desc
        """ % (establecimiento_id)

    r = [dict(e.items() + [('geojson',simplejson.loads(e['geojson']))])
         for e in db.query(q)]

    return flask.Response(flask.json.dumps(r),
                          mimetype='application/json')

@app.route('/matches/<int:establecimiento_id>/<int:escuela_id>/<int:match_id>',
           methods=['PUT'])
def match_modify(establecimiento_id, escuela_id, match_id):
    """ modificar un weighted_match """
    pass

@app.route('/matches/<int:establecimiento_id>', methods=['POST'])
def match_create(establecimiento_id):
    pass

if __name__ == "__main__":
    app.debug = True
    app.run()
