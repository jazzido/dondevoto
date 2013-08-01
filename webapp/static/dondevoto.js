$(function(){
    map = new GMaps({
        div: '#map',
        lat: -12.043333,
        lng: -77.028333,
        mapType: google.maps.MapTypeId.HYBRID
    });

    var table_tmpl = _.template($('#establecimientos-template').html());
    var matches_tmpl = _.template($('#matches-template').html());

    var polygon = null;
    var markers = [];

    var currentBounds = null;

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
            map.fitLatLngBounds(data.bounds.coordinates[0].map(function(p) {
                return new google.maps.LatLng(p[1], p[0]);
            }));

            if (polygon != null) map.removePolygon(polygon);

            currentBounds = data.geojson.coordinates;

            polygon = map.drawPolygon({
                paths: data.geojson.coordinates,
                useGeoJSON: true,
                strokeOpacity: 0.4,
                strokeWeight: 1,
                strokeColor: '#ff0000',
                fillColor: '#BBD8E9',
                fillOpacity: 0.4
            });
        });
    });

    var showMarker = function(e) {
        console.log(e);
    };

    $(document).on({
        'dblclick': function() {
            console.log($(this));
        }
    }, 'tr.matches tr')

    $(document).on(
        {
            'click': function() {
                $('tr', $(this).parent()).removeClass('active');
                $('tr.matches').remove();
                var tr = $(this);
                tr.addClass('active');
                var eid = $(this).data('establecimiento-id');
                $.get('/matches/' + eid,
                      function(data) {

                          if (data.length > 0)
                              $(tr).after(matches_tmpl({matches: data}));

                          map.removeMarkers(markers);
                          markers = []
                          data.forEach(function(m) {
                              var marker = map.addMarker({
                                  lat: m.geojson.coordinates[1],
                                  lng: m.geojson.coordinates[0],
                                  details: m,
                                  infoWindow: {
                                      content: m.nombre
                                  },
                                  click: showMarker,
                              });
                              markers.push(marker);
                          });
                          if (markers.length > 0) map.fitZoom();
                      });
            }
        }, 'table#establecimientos tr.establecimiento');

});
