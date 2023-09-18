from flask import Flask, request, render_template
import os
import random
import redis
import socket
import sys
import logging
from datetime import datetime

# App Insights
from opencensus.ext.azure.log_exporter import AzureLogHandler, AzureEventHandler
from opencensus.ext.azure import metrics_exporter
from opencensus.stats import aggregation as aggregation_module
from opencensus.stats import measure as measure_module
from opencensus.stats import stats as stats_module
from opencensus.stats import view as view_module
from opencensus.tags import tag_map as tag_map_module
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.trace.tracer import Tracer
from opencensus.ext.flask.flask_middleware import FlaskMiddleware
from applicationinsights import TelemetryClient

ConnectionString = 'InstrumentationKey=fb0db209-4b3e-4bf6-94f2-a135944a2b6d;IngestionEndpoint=https://westus2-2.in.applicationinsights.azure.com/'

# Logging
logger = logging.getLogger(__name__)
logger.addHandler(
    AzureEventHandler(
        connection_string=ConnectionString)
)
logger.setLevel(logging.INFO)

# Metrics
exporter = metrics_exporter.new_metrics_exporter(
    enable_standard_metrics=True,
    connection_string=ConnectionString)

# Tracing
tracer = Tracer(
    exporter=AzureExporter(
        connection_string=ConnectionString),
        sampler=ProbabilitySampler(1.0),
)

app = Flask(__name__)

# Requests
middleware = FlaskMiddleware(
    app,
    exporter=AzureExporter(connection_string=ConnectionString),
    sampler=ProbabilitySampler(rate=1.0),
)

# Load configurations from environment or config file
app.config.from_pyfile('config_file.cfg')

if ("VOTE1VALUE" in os.environ and os.environ['VOTE1VALUE']):
    button1 = os.environ['VOTE1VALUE']
else:
    button1 = app.config['VOTE1VALUE']

if ("VOTE2VALUE" in os.environ and os.environ['VOTE2VALUE']):
    button2 = os.environ['VOTE2VALUE']
else:
    button2 = app.config['VOTE2VALUE']

if ("TITLE" in os.environ and os.environ['TITLE']):
    title = os.environ['TITLE']
else:
    title = app.config['TITLE']

# Redis Connection
# r = redis.Redis()

redis_server = os.environ['REDIS']

# Redis Connection to another container
try:
   if "REDIS_PWD" in os.environ:
      r = redis.StrictRedis(host=redis_server,
                        port=6379,
                        password=os.environ['REDIS_PWD'])
   else:
      r = redis.Redis(redis_server)
   r.ping()
except redis.ConnectionError:
   exit('Failed to connect to Redis, terminating.')
   
# Change title to host name to demo NLB
if app.config['SHOWHOST'] == "true":
    title = socket.gethostname()

# Init Redis
if not r.get(button1): r.set(button1,0)
if not r.get(button2): r.set(button2,0)

@app.route('/', methods=['GET', 'POST'])
def index():
    with tracer.span(name="index") as span:  # Trace the index function
        if request.method == 'GET':
            with tracer.span(name="get_votes"):  # Trace the GET method operations
                vote1 = r.get(button1).decode('utf-8')
                vote2 = r.get(button2).decode('utf-8')
            return render_template("index.html", value1=int(vote1), value2=int(vote2), button1=button1, button2=button2, title=title)
        
        elif request.method == 'POST':
            with tracer.span(name="post_votes"):  # Trace the POST method operations
                if request.form['vote'] == 'reset':
                    r.set(button1, 0)
                    r.set(button2, 0)
                    vote1 = r.get(button1).decode('utf-8')
                    vote2 = r.get(button2).decode('utf-8')
                    
                    return render_template("index.html", value1=int(vote1), value2=int(vote2), button1=button1, button2=button2, title=title)
                
                else:
                    vote = request.form['vote']
                    r.incr(vote, 1)
                    vote1 = r.get(button1).decode('utf-8')
                    vote2 = r.get(button2).decode('utf-8')

                    properties = {'custom_dimensions': {vote: 1}}
                    logger.warning(vote, extra=properties)
                    
                    return render_template("index.html", value1=int(vote1), value2=int(vote2), button1=button1, button2=button2, title=title)

if __name__ == "__main__":

    # app.run() # local

     app.run(host='0.0.0.0', threaded=True, debug=True) # remote