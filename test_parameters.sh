# Django
export DEBUG="TRUE"
export SECRET_KEY='8540'
export DJANGO_SETTINGS_MODULE='core.settings'

# Logging
export PUMPWOOD_AUTH_IS_RABBITMQ_LOG="TRUE"

# Database
export DB_USERNAME="pumpwood"
export DB_PASSWORD='pumpwood'
export DB_HOST="0.0.0.0"
export DB_PORT="7000"
export DB_DATABASE="pumpwood"

# Microservice
export MICROSERVICE_NAME='microservice-auth'
export MICROSERVICE_URL='http://localhost:8085'
export MICROSERVICE_USERNAME='microservice--auth'
export MICROSERVICE_PASSWORD='microservice--auth'
export MICROSERVICE_SSL='False'

# RabbitMQ
export RABBITMQ_QUEUE=""
export RABBITMQ_USERNAME='pumpwood'
export RABBITMQ_PASSWORD='pumpwood'
export RABBITMQ_HOST='localhost'
export RABBITMQ_PORT='5672'

# Kong
export CLOUD="FALSE"
export SERVICE_URL="http://pumpwood-auth-app:5000/"
export API_GATEWAY_URL="http://0.0.0.0:8001/"
