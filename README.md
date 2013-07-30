dondevoto
=========

**dondevoto** es un intento de construir un mapa de los locales de votación para las Primarias Abiertas Simultáneas y Obligatorias (PASO) para el año 2013. El sitio [padron.gob.ar](http://www.padron.gob.ar) muestra la ubicación de los locales de votación una vez realizada una consulta. Esto indica que alguna dependencia estatal tiene una base de datos como la que estamos intentando construir, pero no hemos podido encontrarla y nada indica que haya sido publicada. Si ese mapa en efecto existe, avisen así no trabajamos de más.

La [Dirección Nacional Electoral](http://www.elecciones.gov.ar/default.htm) publicó un [listado de los locales de votación](http://www.elecciones.gov.ar/notificaciones/listado_establecimientos_PASO_2013.pdf). En formato PDF, como no podía ser de otra manera (_¿cuándo van a entender que NO hay que usar PDF para publicar datos?_).

Procesamos ese archivo con [Tabula](http://tabula.nerdpower.org) para convertirlo a un formato usable. Tabula todavía no es perfecto y hubo que acomodar un poco su output, pero nada del otro mundo.

## Primer intento

Una vez que tuvimos la información en CSV, formato apropiado para el intercambio y publicación de datos de este tipo, subimos [el archivo a Google Fusion Tables](https://www.google.com/fusiontables/data?docid=1EJrlVnMDHN8tIeEIyFC4IpnJ8T1_VAmleWmA2nE#rows:id=1) y procesamos los registros con el _geocoder_. Falló estrepitosamente. La razón es la gran inconsistencia en el formato y contenido de las direcciones de los locales. Algunos ejemplos:

  - _"AGUIRRE E/STORNI Y DE LA  VEGA,B° LOS ALAMOS - GLEW"_
  - _"ROSARIO Y BOLIVAR S/N°,B° RAYO DE SOL - LON"_

Descartado el geocoder.

## Segundo intento

En Argentina, las escuelas suelen servir como locales de votación. Hay excepciones (municipalidades, sociedades de fomento), pero podemos asumir con alto grado de certeza que un establecimiento (los publicados por DNE) va a corresponderse con una escuela. Este segundo intento consistió en intentar _matchear_ cada local de votación con una escuela.

### Hurgando en mapaeducativo.edu.ar

El [Mapa Educativo][http://www.mapaeducativo.edu.ar] es un gran recurso de información sobre el sistema educativo argentino, confeccionado por el Ministerio de Educación de la Nación.

```bash
for i in `seq 1 1000 60000`; do ogr2ogr -append -f "ESRI Shapefile" escuelas WFS:"http://www.mapaeducativo.edu.ar/geoserver/ows?service=wfs&version=1.0.0&sortBy=gid&startIndex=$i" men:escuelas_oferta; done
```
