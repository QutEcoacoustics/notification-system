import json
import datetime
from toad_functions import templateReport
from jinja2.exceptions import TemplateError, TemplateSyntaxError

with open("sensors_status.json", "r", encoding = 'utf-8') as f:
    full_report = json.loads(f.read())

with open("sensors_status.template.html", 'r', encoding = 'utf-8') as f:
    viewer_template = f.read()

try:
    target_date = datetime.date(2018, 8, 1)
    report = templateReport(viewer_template, full_report, target_date)
except TemplateSyntaxError as template_error:
    print(f"Templating error: {template_error.message}, line:{template_error.lineno}")
    raise

with open("sensors_status.html", 'w', encoding = 'utf-8') as f:
    f.write(report)