# PumpWood Django Views
Assists creation of django views in a Pumpwood pattern. It make it possible
to use
<a href="https://github.com/Murabei-OpenSource-Codes/pumpwood-communication">
    pumpwood-communication
</a> to communicate with end-points.

<p align="center" width="60%">
  <img src="doc/sitelogo-horizontal.png" /> <br>

  <a href="https://en.wikipedia.org/wiki/Cecropia">
    Pumpwood is a native brasilian tree
  </a> which has a symbiotic relation with ants (Murabei)
</p>

## Quick start
PumpWoodRestService helps creating 

```
from .views import PumpWoodRestService

class RestUser(PumpWoodRestService):
    """End-point with information about Pumpwood users."""

    endpoint_description = "Users"
    notes = "End-point with user information"
    dimensions = {
        "microservice": "pumpwood-auth-app",
        "service_type": "core",
        "service": "auth",
        "type": "user",
    }
    icon = None

    service_model = User
    serializer = SerializerUser
    list_fields = [
        "pk", "model_class", 'username', 'email', 'first_name',
        'last_name', 'last_login', 'date_joined', 'is_active', 'is_staff',
        'is_superuser', 'is_microservice', 'dimensions', 'extra_fields',
        'all_permissions', 'group_permissions', 'user_profile']
    foreign_keys = {}

```
