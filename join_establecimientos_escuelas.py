import sys
from difflib import *
import heapq
from datetime import datetime
import Queue
import threading
import csv

import dataset

def get_close_matches_with_score(word, possibilities, n=3, cutoff=0.6):
    """ Lo mismo que difflib.get_close_matches
        pero tambien retorna el score """
    if not n >  0:
        raise ValueError("n must be > 0: %r" % (n,))
    if not 0.0 <= cutoff <= 1.0:
        raise ValueError("cutoff must be in [0.0, 1.0]: %r" % (cutoff,))
    result = []
    s = SequenceMatcher()
    s.set_seq2(word)
    for x in possibilities:
        s.set_seq1(x)
        if s.real_quick_ratio() >= cutoff and \
           s.quick_ratio() >= cutoff and \
           s.ratio() >= cutoff:
            result.append((s.ratio(), x))

    # Move the best scorers to head of list
    result = heapq.nlargest(n, result)
    return result


def memoize(f):
    """ Memoization decorator for functions taking one or more arguments. """
    class memodict(dict):
        def __init__(self, f):
            self.f = f
        def __call__(self, *args):
            return self[args]
        def __missing__(self, key):
            ret = self[key] = self.f(*key)
            return ret
    return memodict(f)

# mapeo de nombres de provincias desde los nombres usados por
# el listado de establecimientos de DiNE al listado
# de escuelas de mapaeducativo.edu.ar
establecimientos_escuelas = {u'BUENOS AIRES': u'Buenos Aires',
 u'CAPITAL FEDERAL': u'CIUDAD DE BUENOS AIRES',
 u'CATAMARCA': u'Catamarca',
 u'CHACO': u'CHACO',
 u'CHUBUT': u'Chubut',
 u'CORRIENTES': u'Corrientes',
 u'C\xd3RDOBA': u'Crdoba',
 u'ENTRE R\xcdOS': u'ENTRE RIOS',
 u'FORMOSA': u'Formosa',
 u'JUJUY': u'Jujuy',
 u'LA PAMPA': u'La Pampa',
 u'LA RIOJA': u'LA RIOJA',
 u'MENDOZA': u'Mendoza',
 u'MISIONES': u'Misiones',
 u'NEUQU\xc9N': u'Neuqun',
 u'R\xcdO NEGRO': u'Ro Negro',
 u'SALTA': u'Salta',
 u'SAN JUAN': u'SAN JUAN',
 u'SAN LUIS': u'San Luis',
 u'SANTA CRUZ': u'SANTA CRUZ',
 u'SANTA FE': u'Santa Fe',
 u'SANTIAGO DEL ESTERO': u'Santiago del Estero',
 u'TIERRA DEL FUEGO': u'Tierra del Fuego',
 u'TUCUM\xc1N': u'TUCUMAN'}

db = dataset.connect('postgresql://manuel@localhost:5432/mapa_paso')
dine_estab = db['establecimientos']
escuelas = db['escuelasutf8']
weighted_matches = db['weighted_matches']

@memoize
def all_escuelas():
    list(escuelas)

@memoize
def escuelas_provincia(provincia):
    """ Listado de escuelas por provincia
        provincia: nombre pcia segun escuelasutf8 """
    return list(db.query(escuelas.table.select(escuelas.table.c.provincia == provincia)))

@memoize
def escuelas_string_match(provincia, match_in):
    return set([canon("%(ndomiciio)s%(localidad)s" % e)
                for e in match_in])

@memoize
def escuelas_in_codigo_postal(codigo_postal):
   # q obtiene todas las escuelas dentro de `codigo_postal`
    q = """ select e.* from escuelasutf8 e, cp_geometries
            where cp_geometries.cp = '%s'
            and st_within(wkb_geometry_4326, cp_geometries.geom)
    """ % (codigo_postal)
    return [escuela for escuela in db.query(q)]

@memoize
def escuelas_in_distrito(dne_seccion_id, dne_distrito_id):
    q = """ select * from escuelasutf8 where
            st_within(wkb_geometry_4326, (select st_collect(o.wkb_geometry) as geom
            from divisiones_administrativas o
            where o.dne_seccion_id = %s
              and o.dne_distrito_id = %s
            group by o.wkb_geometry))
        """ % (dne_seccion_id, dne_distrito_id)

    return list(db.query(q))


def log(msg):
    print >>sys.stderr, msg

def canon(s):
    return s.lower().replace(' ', '')

persist_queue = Queue.Queue()
def match_persister():
#    d = csv.DictWriter(sys.stdout, ['establecimiento_id', 'escuela_id', 'score'])
    while True:
        establecimiento, matches = persist_queue.get()
        for m in matches:
            weighted_matches.insert({
                'establecimiento_id': establecimiento['id'],
                'escuela_id': m[1]['ogc_fid'],
                'score': m[0]
            })
        persist_queue.task_done()

def do_match():
    total_establecimientos = len(dine_estab)
    log('TOTAL: %s' % total_establecimientos)
    match_count = 0
    current_item = 0
    current_time = datetime.now()

    for e in dine_estab:
        match_in = []
        canon_func = None

        matches = []
        coeff = 1

        if current_item % 1000 == 0:
            log('processing item %i/%i (+%s seconds)' % (current_item, total_establecimientos, (datetime.now() - current_time).seconds))
            current_time = datetime.now()

        current_item += 1


        canon_func = lambda est: canon("%(nombre)s%(ndomiciio)s") % { str(k):v for k,v in est.iteritems() }
        match_in = { canon_func(i): i
                     for i in escuelas_in_distrito(e['dne_seccion_id'],
                                                   e['dne_distrito_id']) }

        _matches = get_close_matches_with_score(canon_func({'nombre': e[u'establecimiento'],
                                                            'ndomiciio': e[u'direccion']}),
                                                match_in.keys(),
                                                5,
                                                0.5)

        matches += [(score * coeff, match_in[result]) for score, result in _matches]

        # log('Matching "%s - %s (%s)"' % (e['establecimiento'], e['direccion'], e['localidad']))
        # for m in matches:
        #     log('\t%.2f %s - %s (%s)' % (m[0], m[1]['nombre'], m[1]['ndomiciio'], m[1]['localidad']))

        persist_queue.put((e, matches))


def _do_match():
    total_establecimientos = len(dine_estab)
    log('TOTAL: %s' % total_establecimientos)
    match_count = 0
    current_item = 0
    current_time = datetime.now()

    # # e == centro de votacion de la lista de DINE
#    for e in dine_estab:
    for e in db.query(dine_estab.table.select(dine_estab.table.c.id > 135)):
        match_in = []
        canon_func = None

        matches = []
        coeff = 1

        if current_item % 300 == 0:
            log('processing item %i/%i (+%s seconds)' % (current_item, total_establecimientos, (datetime.now() - current_time).seconds))
            current_time = datetime.now()

        current_item += 1

        if e['codigo_postal'] != '':
            # si tengo codigo postal, restringir el espacio de busqueda

            canon_func = lambda est: canon("%(nombre)s%(ndomiciio)s") % { str(k):v for k,v in est.iteritems() }
            match_in = { canon_func(i): i for i in escuelas_in_codigo_postal(e['codigo_postal']) }

            _matches = get_close_matches_with_score(canon_func({'nombre': e[u'establecimiento'],
                                                                'ndomiciio': e[u'direccion']}),
                                                    match_in.keys(),
                                                    5)

            matches += [(score * coeff, match_in[result]) for score, result in _matches]

        if e['distrito'] != '':
            # no tengo codigo postal, usar la provincia

            coeff = 0.5
            canon_func = lambda est: canon("%(nombre)s%(ndomiciio)s%(localidad)s") % { str(k):v for k,v in est.iteritems() }
            match_in = { canon_func(i): i
                         for i in escuelas_provincia(establecimientos_escuelas[e['distrito']]) }

            _matches = get_close_matches_with_score(canon_func({'nombre': e[u'establecimiento'],
                                                                'ndomiciio': e[u'direccion'],
                                                                'localidad': e[u'localidad']}),
                                                    match_in.keys(),
                                                    5)

            matches += [(score * coeff, match_in[result])
                        for score, result in _matches
                        if result not in [m[1] for m in matches]]

        else:
            # ni provincia tengo, buscar en todo el espacio
            match_in = all_escuelas()
            canon_func = lambda est: "%(establecimiento)s%(direccion)s%(localidad)s" % est

        if matches > 0:
            match_count += 1

        persist_queue.put((e, matches))

    log('matches: %s' % match_count)

if __name__ == '__main__':
    t_main = threading.Thread(target=do_match)
    t_persister = threading.Thread(target=match_persister)
    t_main.daemon = True; t_persister.daemon = True
    t_main.start(); t_persister.start()

    for t in [t_main,t_persister]: t.join()
