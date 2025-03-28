import json
import pytest
from grafana_libsonnet import convert

test_json = {}
with open("tests_libsonnet/test-input.json", "r") as f:
    test_json = json.load(f)


EXPECTED_OUTPUT = """local g = import 'grafonnet/grafana.libsonnet';


(import 'utils.libsonnet') {
  'test': $.dashboardSchema(
    '',
    '',
    "",
    "now-6h",
    "", 
    "",
    $._config.dashboardTags,
    ''
  )"""


def test_annotation():
    input_json = {
        "annotations": test_json["annotations"],
        "time": test_json["time"],
        "templating": [],
        "panels": [],
    }
    output_libsonnet = convert(input_json, "test")
    expected_libsonnet = (
        EXPECTED_OUTPUT
        + """
  .addAnnotation(
      $.addAnnotationSchema(
        1,
        -- Grafana --,
        True,
        True,
        'rgba(0, 211, 255, 1)',
        'Annotations & Alerts',
        'dashboard'
      )
  )
  .addPanels([
  ])


}"""
    )
    assert output_libsonnet == expected_libsonnet


def test_stat_panel():
    input_json = {
        "annotations": {},
        "time": test_json["time"],
        "templating": [],
        "panels": [p for p in test_json["panels"] if p.get("type") == "stat"],
    }
    output_libsonnet = convert(input_json, "test")
    expected_libsonnet = (
        EXPECTED_OUTPUT
        + """
  
  .addPanels([
      $.addStatPanel(
        title='Stat',
        description='desc',
        unit='',
        datasource='$datasource',
        gridPosition={ x: 0, y: 1, w: 3, h: 3 },
        colorMode="background",
        graphMode="none",
        justifyMode="auto",
        orientation="auto",
        textMode="auto",
        interval='1m',
        color={ mode: 'thresholds' },
        thresholdsMode='',
        noValue=null,
      ).addThresholds([
        { color: 'dark-green', value: null },
      ])
      .addTarget(
        $.addTargetSchema(
          expr="promql_query",
          format='table',
          instant=true,
          legendFormat=""__auto"",
          range=false,
          datasource='$datasource',
        )
      ),

  ])


}"""
    )
    print(output_libsonnet)
    assert output_libsonnet == expected_libsonnet
