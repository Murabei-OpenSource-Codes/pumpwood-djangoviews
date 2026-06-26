# PumpWood Django Views
Assists creation of django views in a Pumpwood pattern. It make it possible
to use
<a href="https://github.com/Murabei-OpenSource-Codes/pumpwood-communication">
    pumpwood-communication
</a> to communicate with end-points.

<p align="center" width="60%">
  <img src="static_doc/sitelogo-horizontal.png" /> <br>

  <a href="https://en.wikipedia.org/wiki/Cecropia">
    Pumpwood is a native brasilian tree
  </a> which has a symbiotic relation with ants (Murabei)
</p>

## Documentation
For docs, check [doc page](https://murabei-opensource-codes.github.io/pumpwood-djangoviews/pumpwood-djangoviews/src/pumpwood_djangoviews.html).

## fill_options defaults

Views based on ``PumpWoodRestService`` expose ``fill_options`` and
``cls_fields_options``. Each field description includes a ``default``
key serialized through ``pumpwood-communication`` sentinel markers:

- ``**missing**`` — no default; the client must supply a value.
- ``**autoincrement**`` — database-generated primary key.
- ``**now**`` — server datetime; ``DateTimeField`` with ``auto_now``,
  ``auto_now_add``, or ``default=timezone.now``.
- ``**today**`` — server date; ``DateField`` with ``auto_now``,
  ``auto_now_add``, or ``default=date.today``.

Model ``auto_now`` and ``auto_now_add`` flags take precedence over DRF
serializer defaults. Callable defaults such as ``timezone.now`` are
normalized to ``**now**`` instead of being evaluated at request time.

Responses may be cached; clear the fill_options cache or wait for
``INFO_CACHE_TIMEOUT`` after upgrading this package.
