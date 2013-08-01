$(function(){
    map = new GMaps({
        div: '#map',
        lat: -12.043333,
        lng: -77.028333,
        mapType: google.maps.MapTypeId.HYBRID
    });

    var table_tmpl = _.template($('#establecimientos-template').html());
    var matches_tmpl = _.template($('#matches-template').html());
    var infowindow_tmpl = _.template($('#infowindow-template').html());

    var polygon = null;
    var markers = [];

    var currentBounds = null;
    var currentMarker = null;

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

        }
    }, 'tr.matches tr')

    $(document).on({
        'change': function() {
            var chk = $(this);
            var establecimiento = chk
                .parents('.matches')
                .prev()
                .data('establecimiento-id');
            var place = chk
            .parents('tr:not(.matches)').data('place');
            if (chk.is(':checked')) {
                $.post('/matches/' + establecimiento + '/' + place.ogc_fid);
            }
        },
    }, 'tr.matches tr input[type=checkbox]')


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

                          if (data.length > 0) {
                              tr.after(matches_tmpl({matches: data}));
                              $('tr', tr.next()).each(function(i, t) {
                                  $(this).data('place', data[i]);
                              })
                          }

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
                      });
            }
        }, 'table#establecimientos tr.establecimiento');

    $(document).on("ajaxStart", function(e, xhr, settings, exception)  {
        console.log('ajaxstart');
    });

    $(document).on("ajaxComplete", function(e, xhr, settings, exception)  {
        console.log('ajaxend');
    });

});
