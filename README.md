dondevoto
=========

**dondevoto** es un intento de construir un mapa de los locales de votación para las Primarias Abiertas Simultáneas y Obligatorias (PASO) para el año 2013. El sitio [padron.gob.ar](http://www.padron.gob.ar) muestra la ubicación de los locales de votación una vez realizada una consulta. Esto indica que alguna dependencia estatal tiene una base de datos como la que estamos intentando construir, pero no hemos podido encontrarla y nada indica que haya sido publicada. Si ese mapa en efecto existe y es público, avisen así no trabajamos de más.

La [Dirección Nacional Electoral](http://www.elecciones.gov.ar/default.htm) publicó un [listado de los locales de votación](http://www.elecciones.gov.ar/notificaciones/listado_establecimientos_PASO_2013.pdf). En formato PDF, como no podía ser de otra manera _(¿cuándo van a entender que NO hay que usar PDF para publicar datos?)_.

Procesamos ese archivo con [Tabula](http://tabula.nerdpower.org) para convertirlo a un formato usable. Tabula todavía no es perfecto y hubo que acomodar un poco su output, pero nada del otro mundo. En pocos minutos logramos un conjunto de datos _sano_, que contiene toda la información antes atrapada en PDF.

## Primer intento — Google Geocoder

Una vez que tuvimos la información en CSV, formato apropiado para el intercambio y publicación de datos de este tipo, subimos [el archivo a Google Fusion Tables](https://www.google.com/fusiontables/data?docid=1EJrlVnMDHN8tIeEIyFC4IpnJ8T1_VAmleWmA2nE#rows:id=1) y procesamos los registros con el _geocoder_. Falló estrepitosamente. La razón es la gran inconsistencia en el formato y contenido de las direcciones de los locales. Algunos ejemplos:

  - _"AGUIRRE E/STORNI Y DE LA  VEGA,B° LOS ALAMOS - GLEW"_
  - _"ROSARIO Y BOLIVAR S/N°,B° RAYO DE SOL - LON"_

Descartado el geocoder.

## Segundo intento — Combinando fuentes

En Argentina, las escuelas suelen servir como locales de votación. Hay excepciones (municipalidades, sociedades de fomento), pero podemos asumir con alto grado de certeza que un establecimiento (los publicados por DNE) va a corresponderse con una escuela. Este segundo intento consistió en intentar _matchear_ cada local de votación con una escuela. Pero nos hace falta conseguir un listado de escuelas que contenga su ubicación geográfica.

### Hurgando en mapaeducativo.edu.ar

El [Mapa Educativo](http://www.mapaeducativo.edu.ar) es un gran recurso de información sobre el sistema educativo argentino, confeccionado por el Ministerio de Educación de la Nación.

El sitio contiene un [mapa con la ubicación _precisa_ de todos los establecimientos educativos del país](http://www.mapaeducativo.edu.ar/mapserver/aen/educacion/localizar/index.php), justo lo que necesitamos. El mapa en cuestión está implementado con un GeoServer que expone un [Web Mapping Service](http://docs.geoserver.org/stable/en/user/services/wms/reference.html), es decir un servidor de _tiles_. Los _tiles_ son imágenes (mosaicos) que, combinados, componen un mapa parecido a los de Google Maps.

Esas imágenes no pueden darnos la información que necesitamos (datos de las escuelas y su ubicación geográfica). Miramos un poco más de cerca y "descubrimos" que ese mismo GeoServer también expone un servicio [Web Feature Service](http://docs.geoserver.org/latest/en/user/services/wfs/) (WFS). Bingo.

Los _layers_ en WFS contienen datos vectoriales, es decir, _geometrías_ con atributos. Vimos que el _layer_ que contiene los datos que necesitamos es `men:escuelas_oferta` y los transferimos a un Shapefile con [`ogr2ogr`](https://www.google.com.ar/search?q=ogr2ogr&oq=ogr2ogr&aqs=chrome.0.69i57j69i59l3j69i61l2.1638j0&sourceid=chrome&ie=UTF-8), parte del proyecto [GDAL](http://www.gdal.org/):

```bash
for i in `seq 1 1000 60000`;
  do ogr2ogr -append -f "ESRI Shapefile" escuelas WFS:"http://www.mapaeducativo.edu.ar/geoserver/ows?service=wfs&version=1.0.0&sortBy=gid&startIndex=$i" men:escuelas_oferta;
done
```

_(Este WFS entrega hasta 1000 features por pedido y el layer contiene ~60k features. Por eso el loop.)_

### Establecimientos → Escuelas

Para laburar más cómodos, cargamos los datasets que tenemos hasta ahora en un PostgreSQL + PostGIS, valiéndonos de la librería [dataset](http://github.com/pudo/dataset). En este punto, contamos con dos tablas en nuestra DB:

  - `establecimientos` (los locales de votación originalmente publicados en PDF)
  - `escuelas` (las escuelas georeferenciadas obtenidas del WFS de mapaeducativo.edu.ar)

La idea era implementar un _matching aproximado_ entre el nombre, dirección, localidad y provincia de los `establecimientos` y los mismos campos de la tabla `escuelas`. Esto lo implementamos con la función `get_close_matches` de [difflib](http://docs.python.org/library/difflib.html), parte de la librería estándar de Python.

Mejoró notablemente la precisión del matching con respecto al primer intento, pero todavía teníamos muchos falsos positivos. Por ejemplo, hay muchas escuelas en el país que se llaman "Colegio Manuel Belgrano" y como nuestro matching es _fuzzy_, tenemos baja precisión.

## Tercer intento — Restringiendo el espacio de búsqueda

Notamos que la lista de establecimientos de votación (la tabla `establecimientos`) tiene dos campos interesantes: `codigo_distrito` y `seccion`. Le preguntamos a la máxima autoridad electoral de la Internet que es [Andy Tow](https://twitter.com/andy_tow) y nos aseguró que `codigo_distrito` es un código correspondiente a cada provincia y la `seccion` es un número de cada partido, departamento o comuna, definido por el Código Nacional Electoral.

También contamos con la ayuda de [Gonzalo Iglesias](https://twitter.com/gonzaloiglesias), otro gran héroe de la información pública que hace tiempo confeccionó una suerte de [_Piedra Rosetta_ de información distrital](https://www.google.com/fusiontables/DataSource?docid=1020i2cUGopm4LepAPtFFG9EgsFDIfRNWTQ44oOg). Uno de los campos de esa tabla, es `DNE_ID` y se corresponde con los campos `codigo_distrito` y `seccion` de nuestra tabla `establecimientos`! Esto quiere decir que ahora podemos saber con seguridad en qué partido, departamento o comuna está cada local de votación.

Importamos esos datos a una nueva tabla en nuestro Postgres: `divisiones_administrativas`

Podemos aprovecharnos de ese hecho para mejorar el segundo intento y _restringir el espacio de búsqueda_: en vez de intentar nuestro fuzzy matching sobre toda la tabla `escuelas`, obtenemos las `escuelas` contenidas geográficamente en el distrito y sección del establecimiento y _matcheamos_ en ese espacio. Subyace a esto la suposición de que en cada distrito los nombres y direcciones de las escuelas van a ser "suficientemente distintos" entre sí.

Hubo otro salto muy grande en la precisión, pero todavía no es perfecto. Y nunca lo va a ser.

## Y qué hacemos?

Si llegaste hasta acá es porque te interesa el problema y quizás te interese colaborar. Si querés ver qué hice:

  - Importá el dump [dondevoto.sql.bz2](http://dump.jazzido.com/dondevoto.sql.bz2) a un Postgres + PostGIS
  - Hay una tabla `weighted_matches`: vincula `establecimientos` (lugares de votacion) con `escuelas` (puntos en el mapa), atribuído con un grado de certeza del match (retornado por `difflib`).
  - El script `join_establecimientos_escuelas.py` es el que construye esa tabla. Si cambiás el algoritmo que la construye, truncala antes de correrlo.

Es probable que la información la que contamos hasta ahora contenga bastantes pistas con las que definir reglas o heurísticas que permitan mejorar la precisión del (rudimentario) matching que venimos haciendo hasta ahora. Hay establecimientos que nunca vamos a poder referenciar con la información disponible: por ejemplo, locales de votación que _no_ son escuelas. No va a quedar otra más que trabajo manual, también son bienvenidas ideas sobre eso (aplicación para _crowdsourcear_ la validación/entrada de info?).

## Tanto laburo para qué?

Contar con un mapa completo de locales de votación puede servir, en el futuro, para varias cosas. Una de ellas: visualización de resultados electorales a gran resolución (nivel circuito electoral).

Y por otro lado, por que sí.

Entonces, si tenés ganas de ver qué sale, contactame: [@manuelaristaran](http://twitter.com/manuelaristaran) en Twitter o a mi mail, que figura en [jazzido.com](http://jazzido.com)
