from django.contrib import admin

from .models import (
    Organization,
    PackingStation,
    StationDenominationEfficiency,
    StationDenominationSupport,
    TransferSegment,
    TransportRoute,
)

admin.site.register(TransportRoute)
admin.site.register(Organization)
admin.site.register(PackingStation)
admin.site.register(StationDenominationSupport)
admin.site.register(StationDenominationEfficiency)
admin.site.register(TransferSegment)
