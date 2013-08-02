$(function(){
    map = new GMaps({
        div: '#map',
        lat: -12.043333,
        lng: -77.028333,
        mapType: google.maps.MapTypeId.HYBRID,
        mapTypeControlOptions: {
            mapTypeIds : ["hybrid", "roadmap", "satellite", "terrain", "osm"]
        }
    });

    map.addMapType("osm", {
        getTileUrl: function(coord, zoom) {
            return "http://tile.openstreetmap.org/" + zoom + "/" + coord.x + "/" + coord.y + ".png";
        },
        tileSize: new google.maps.Size(256, 256),
        name: "OpenStreetMap",
        maxZoom: 18
    });

    map.setContextMenu({
        control: 'map',
        options: [{
            title: 'Agregar centro de votación aquí',
            name: 'agregar_lugar',
            action: function(e) {

            }
        }]
    });

    var table_tmpl = _.template($('#establecimientos-template').html());
    var matches_tmpl = _.template($('#matches-template').html());
    var infowindow_tmpl = _.template($('#infowindow-template').html());
    var completion_tmpl = _.template($('#completion-template').html());

    var polygon = null;
    var markers = [];

    var maxZoomService = new google.maps.MaxZoomService();

    var currentBounds = null;
    var currentMarker = null;

    completionRankingInterval = window.setInterval(function() {
        $.get('/completion', function(provincias) {
            $('#provincia-ranking').html(completion_tmpl({provincias:provincias}));
        })
    }, 5000);

    $('select#distrito').on('change', function() {
        var p_d = $(this).val().split('-');
        $.get('/establecimientos/' + p_d.join('/'),
              function(data) {
                  $('table#establecimientos')
                      .html(table_tmpl({establecimientos: data }));
              });

        map.removeMarkers(markers);
        markers = []

        $.get('/seccion/' + p_d.join('/'), function(data) {
            currentBounds = data.bounds.coordinates[0].map(function(p) {
                return new google.maps.LatLng(p[1], p[0]);
            });
            map.fitLatLngBounds(currentBounds);

            if (polygon != null) map.removePolygon(polygon);

            polygon = map.drawPolygon({
                paths: data.geojson.coordinates,
                useGeoJSON: true,
                strokeOpacity: 0.2,
                strokeWeight: 1,
                strokeColor: '#ff0000',
                fillColor: '#BBD8E9',
                fillOpacity: 0.4,
                clickable: false
            });
        });
    });

    var showMarker = function(e) {
        console.log(e);
    };

    $(document).on({
        'mouseover': function() {
            if (currentMarker) {
                currentMarker.infoWindow.close();
            }
            var d = $(this).data('place');
            currentMarker = _.find(map.markers, function(m) {
                return m.details == d;
            });
            currentMarker.infoWindow.open(map, currentMarker);
        },
        'mouseout': function() {

        },
        'dblclick': function() {
            console.log(currentMarker);
        }
    }, 'tr.matches tr')

    $(document).on({
        'change': function() { // checkbox para elegir un match
            var chk = $(this);

            var establecimiento_tr = chk
                .parents('.matches')
                .prev();

            var establecimiento = establecimiento_tr
                .data('establecimiento-id');

            var place = chk
                .parents('tr:not(.matches)')
                .data('place');

            var url = '/matches/' + establecimiento + '/' + place.ogc_fid;

            if (chk.is(':checked')) {
                establecimiento_tr.addClass('matched');
                $.post(url);
            }
            else { //delete
                // indicar que no hay match sólo si no hay ningun
                // chkbox activado
                if (!$('input[type=checkbox]').is(':checked'))
                    establecimiento_tr.removeClass('matched');

                $.post(url, { _method: 'delete'});
            }
        },
    }, 'tr.matches tr input[type=checkbox]')


    $(document).on(
        {
            // click en establecimiento, abre los matches
            'click': function() {

                // saco el poligono, para que no me capture el puto rightclick
//                map.removePolygon(polygon);
                $('tr', $(this).parent()).removeClass('active');
                $('tr.matches').remove();
                var tr = $(this);
                tr.addClass('active');
                var eid = $(this).data('establecimiento-id');
                $.get('/matches/' + eid,
                      function(data) {

                          // todo este quilombo es para sacar los duplicados que vienen del join
                          data =
                              _.sortBy(
                                  _.map(
                                      _.pairs(
                                          _.groupBy(data,
                                                    function(d) {
                                                        return d.ogc_fid;
                                                    }, data)
                                      ), function(p) {
                                          return _.max(p[1],
                                                       function(d) {
                                                           return d.score;
                                                       });
                                      }),
                                  function(d) {
                                      return -d.score;
                                  });


                          tr.after(matches_tmpl({
                              matches: data,
                              seccion: $('select#distrito option:selected').html(),
                              distrito: $('select#distrito option:selected').parent().attr('label')
                          }));
                          $('tr', tr.next()).each(function(i, t) {
                              $(this).data('place', data[i]);
                          });

                          if (_.some(data, function(d) { return d.score == 1}))
                              tr.addClass('matched');

                          map.removeMarkers(markers);
                          markers = []
                          data.forEach(function(m) {
                              var marker = map.addMarker({
                                  lat: m.geojson.coordinates[1],
                                  lng: m.geojson.coordinates[0],
                                  details: m,
                                  infoWindow: {
                                      content: infowindow_tmpl({place: m})
                                  },
                                  click: showMarker,
                              });
                              markers.push(marker);
                          });
                          if (markers.length > 0) map.fitZoom();

                          // Agrego el geocomplete
                          $('input[type=text]', tr.next())
                              .geocomplete({ bounds: polygon.getBounds() })
                              .bind("geocode:result", function(event, result) {
                                  if (!polygon.getBounds().contains(result.geometry.location))
                                      // no salir de los bounds actuales si el geocoder
                                      // retorna algo afuera de esos bounds
                                      return;
                                  maxZoomService.getMaxZoomAtLatLng(result.geometry.location, function(r) {
                                      if (r.status == google.maps.MaxZoomStatus.OK)
                                          map.setZoom(r.zoom);
                                      map.map.panTo(result.geometry.location);
                                  });

                              });
                      });
            }
        }, 'table#establecimientos tr.establecimiento');

    $(document).on("ajaxSend", function(e, xhr, settings, exception)  {
        if (settings.url == '/completion') return;
        $('#loading').css('visibility', 'visible');
    });

    $(document).on("ajaxComplete", function(e, xhr, settings, exception)  {
        $('#loading').css('visibility', 'hidden');
    });

});
