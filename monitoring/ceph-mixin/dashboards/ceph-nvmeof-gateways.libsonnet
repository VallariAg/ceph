local g = import 'grafonnet/grafana.libsonnet';


(import 'utils.libsonnet') {
  'ceph-nvmeof-overview.json': $.dashboardSchema(
    'Ceph NVMe-oF Gateways',
    'Ceph NVMe-oF gateways overview',
    'c4eff735-53a9-4f7d-88ec-fc2d45e2e7d7',
    'now-1h',
    '5s', // TODO 
    13,
    $._config.dashboardTags,
    ''
  ).addAnnotation(
    $.addAnnotationSchema(
      1,
      '-- Grafana --',
      true,  // enable
      true,  // hide
      'rgba(0, 211, 255, 1)',
      'Annotations & Alerts',
      'dashboard'
    )
  ).addRequired( // TODO: see these "addRequired"
    type='grafana', id='grafana', name='Grafana', version='5.3.2'
  ).addRequired(
    type='panel', id='graph', name='Graph', version='5.0.0'
  ).addRequired(
    type='panel', id='heatmap', name='Heatmap', version='5.0.0'
  ).addRequired(
    type='panel', id='singlestat', name='Singlestat', version='5.0.0'
  ).addTemplate(
    g.template.datasource('datasource', 'prometheus', 'default', label='Data Source')
  ).addTemplate(
    $.addClusterTemplate()
  ).addTemplate(
    $.addCustomTemplate(
      name='interval',
      query='5s,10s,30s,1m,10m,30m,1h,6h,12h,1d,7d,14d,30d',
      current='$__auto_interval_interval',
      refresh=2,
      label='Interval',
      auto_count=10,
      auto_min='1m',
      options=[
        { selected: true, text: 'auto', value: '$__auto_interval_interval' },
        { selected: false, text: '5s', value: '5s' },
        { selected: false, text: '10s', value: '10s' },
        { selected: false, text: '30s', value: '30s' },
        { selected: false, text: '1m', value: '1m' },
        { selected: false, text: '10m', value: '10m' },
        { selected: false, text: '30m', value: '30m' },
        { selected: false, text: '1h', value: '1h' },
        { selected: false, text: '6h', value: '6h' },
        { selected: false, text: '12h', value: '12h' },
        { selected: false, text: '1d', value: '1d' },
        { selected: false, text: '7d', value: '7d' },
        { selected: false, text: '14d', value: '14d' },
        { selected: false, text: '30d', value: '30d' },
      ],
      auto=true,
    )
  ).addTemplate(
      $.addTemplateSchema(
        'gateway', // name 
        '$datasource',
        'label_values(ceph_nvmeof_gateway_info,hostname)', // query definition
        2, // refresh
        false, // include all
        0, // sort
        'Gateway Hostname', // label
        '') // regex
  ).addTemplate(
      $.addTemplateSchema(
        'subsystem',
        '$datasource',
        'label_values(ceph_nvmeof_subsystem_metadata,nqn)',
        1,
        false,
        0,
        'Subsystem NQN',
        '')
  ).addPanels([
      $.addRowSchema(collapse=false, showTitle=true, title='Overview') + { gridPos: { x: 0, y: 0, w: 24, h: 1 } },
      $.addStatPanel(
        title='Gateways',
        unit='none',
        datasource='$datasource',
        gridPosition={ x: 0, y: 1, w: 2, h: 6 },
        colorMode="none",
        graphMode="none",
        justifyMode="auto",
        orientation="auto",
        textMode="auto",
        interval='1m',
        color={ mode: 'thresholds' },
        thresholdsMode='absolute',
        pluginVersion='11.0.0'
      ).addMappings([
        { options: { match: null, result: { index: 1, text: '0' } }, type: 'special' },
      ])
      .addThresholds([
        { color: 'green' },
        { color: 'red', value: 80 },
      ])
      .addTarget($.addTargetSchema(
        expr="count(ceph_nvmeof_gateway_info)",
        format='table',
        instant=true,
        legendFormat="__auto",
        range=false,
        datasource='$datasource',
      )),

      $.addStatPanel(
        title='Reactors per Gateway',
        unit='none',
        datasource='$datasource',
        gridPosition={ x: 2, y: 1, w: 3, h: 6 },
        colorMode="none",
        graphMode="none",
        justifyMode="auto",
        orientation="auto",
        textMode="auto",
        interval='1m',
        color={ mode: 'thresholds' },
        thresholdsMode='absolute',
        pluginVersion='11.0.0'
      ).addMappings([
        { options: { match: null, result: { index: 1, text: '0' } }, type: 'special' },
      ])
      .addThresholds([
        { color: 'green' },
        { color: 'red', value: 80 },
      ])
      .addTarget($.addTargetSchema(
        expr='max(count by(instance) (ceph_nvmeof_reactor_seconds_total{mode=\"busy\"}))',
        format='table',
        instant=true,
        legendFormat="__auto",
        range=false,
        datasource='$datasource',
      )),

      $.addStatPanel(
        title='Subsystems',
        unit='none',
        datasource='$datasource',
        gridPosition={ x: 5, y: 1, w: 2, h: 6 },
        colorMode="none",
        graphMode="none",
        justifyMode="auto",
        orientation="auto",
        textMode="auto",
        interval='1m',
        color={ mode: 'thresholds' },
        thresholdsMode='absolute',
        pluginVersion='11.0.0'
      ).addMappings([
        { options: { match: null, result: { index: 1, text: '0' } }, type: 'special' },
      ])
      .addThresholds([
        { color: 'green' },
        { color: 'red', value: 80 },
      ])
      .addTarget($.addTargetSchema(
        expr="count(count by(nqn) (ceph_nvmeof_subsystem_metadata))",
        format="table",
        instant=true,
        legendFormat="__auto",
        range=false,
        datasource='$datasource',
      )),

      $.addStatPanel(
        title='Subsystem Security',
        description="WARNING if any subsystem is defined with open/no security",
        unit='none',
        decimals=0,
        datasource='$datasource',
        gridPosition={ x: 7, y: 1, w: 3, h: 6 },
        colorMode="background_solid",
        graphMode="none",
        justifyMode="auto",
        orientation="auto",
        textMode="auto",
        interval='1m',
        color={ mode: 'thresholds' },
        thresholdsMode='absolute',
        pluginVersion='11.0.0'
      ).addMappings([
        { options: { match: "null", result: { index: 0, text: 'OK', "color": "dark-green" } }, type: 'special' },
        { options: { from: 1, to: 9999, result: { index: 1, text: 'WARNING', "color": "dark-yellow" } }, type: 'range' },
      ])
      .addTarget($.addTargetSchema(
        expr='count(ceph_nvmeof_subsystem_metadata{allow_any_host=\"yes\"}) ',
        instant=false,
        exemplar=false,
        legendFormat="__auto",
        range=true,
        format='', // does not exist in json, so added ''
        datasource='$datasource',
      )) + { fieldConfig: { defaults: { mappings: [
        { options: { match: "null", result: { index: 0, text: 'OK', "color": "dark-green" } }, type: 'special' },
        { options: { from: 1, to: 9999, result: { index: 1, text: 'WARNING', "color": "dark-yellow" } }, type: 'range' },
      ], thresholds: { mode: 'absolute', steps: [{ color: 'green' }] } } } },

      $.addStatPanel(
        title='Namespaces',
        unit='none',
        datasource='$datasource',
        gridPosition={ x: 10, y: 1, w: 2, h: 6 },
        colorMode="none",
        graphMode="none",
        justifyMode="auto",
        orientation="auto",
        textMode="auto",
        interval='1m',
        color={ mode: 'thresholds' },
        thresholdsMode='absolute',
        pluginVersion='11.0.0'
      ).addMappings([
        { options: { match: null, result: { index: 1, text: '0' } }, type: 'special' },
      ])
      .addThresholds([
        { color: 'green' },
        { color: 'red', value: 80 }
      ])
      .addTarget($.addTargetSchema(
        expr='count(count by(bdev_name) (ceph_nvmeof_bdev_metadata))',
        exemplar=false,
        format='table',
        instant=true,
        legendFormat="__auto",
        range=false,
        datasource='$datasource',
      )),

      $.addStatPanel(
        title='Capacity Exported',
        description="The sum of capacity from all namespaces defined to subsystems",
        unit='bytes',
        datasource='$datasource',
        gridPosition={ x: 12, y: 1, w: 3, h: 6 },
        colorMode="none",
        graphMode="none",
        justifyMode="auto",
        orientation="auto",
        textMode="auto",
        interval='1m',
        color={ mode: 'thresholds' },
        thresholdsMode='absolute',
        pluginVersion='11.0.0'
      ).addMappings([
        { options: { match: 'null', result: { index: 1, text: '0' } }, type: 'special' },
      ])
      .addThresholds([
        { color: 'green', value: null },
        { color: 'red', value: 80 }
      ])
      .addTarget($.addTargetSchema(
        expr='topk(1,sum by(instance) (ceph_nvmeof_bdev_capacity_bytes))',
        exemplar=false,
        format='table',
        instant=true,
        legendFormat="__auto",
        range=false,
        datasource='$datasource',
      )) + { fieldConfig: { defaults: { unit: "bytes" } } },

      $.addStatPanel(
        title='Total IOPS',
        description="All gateways",
        unit='locale',
        datasource='$datasource',
        gridPosition={ x: 15, y: 1, w: 3, h: 6 },
        decimals=0,
        colorMode="none",
        graphMode="area",
        justifyMode="auto",
        orientation="auto",
        textMode="auto",
        interval='1m',
        color={ mode: 'thresholds' },
        thresholdsMode='absolute',
        pluginVersion='11.0.0'
      ).addThresholds([
        { color: 'semi-dark-blue' }
      ])
      .addTarget($.addTargetSchema(
        expr="sum (rate(ceph_nvmeof_bdev_reads_completed_total[30s]) + rate(ceph_nvmeof_bdev_writes_completed_total[30s]))",
        format='',
        instant=false,
        legendFormat="__auto",
        range=true,
        datasource='$datasource',
      )),

      $.addStatPanel(
        title='Total Throughput',
        description="All gateways",
        unit='binBps',
        datasource='$datasource',
        gridPosition={ x: 18, y: 1, w: 3, h: 6 },
        decimals=0,
        colorMode="none",
        graphMode="area",
        justifyMode="auto",
        orientation="auto",
        textMode="auto",
        interval='1m',
        transparent=false, // TODO: maybe remove
        color={ mode: 'thresholds' },
        pluginVersion='11.0.0'
      )
      .addTarget($.addTargetSchema(
        expr="sum (rate(ceph_nvmeof_bdev_read_bytes_total[30s]) + rate(ceph_nvmeof_bdev_written_bytes_total[30s]))",
        format='', 
        instant=false,
        legendFormat="__auto",
        range=true,
        datasource='$datasource',
      )) + { fieldConfig: { defaults: { color: { mode: 'thresholds' }, decimals: 0, unit: 'binBps', thresholds: { mode: 'absolute', steps: [{ color: 'semi-dark-blue', value: 'null' }] } } } },

      $.addGaugePanel(
        title='Busiest Gateway CPU',
        description="Shows the highest average CPU on a gateway within the gateway group",
        gridPosition={ h: 6, w: 3, x: 21, y: 1 },
        unit='percentunit',
        // TODO add: orientation="auto",
        max=100,
        min=0,
        // TODO add: decimals=2,
        // TODO add: thresholdsMode='percentage',
        // TODO add: color={ mode: 'thresholds' },
        interval='1m',
        pluginVersion='11.0.0'
      )
      .addThresholds([
        { color: 'green' },
        { color: '#EAB839', value: 70 },
        { color: 'red', value: 80 },
      ])
      .addTarget($.addTargetSchema(
        expr='max(avg by(instance) (rate(ceph_nvmeof_reactor_seconds_total{mode="busy"}[1m])))',
        instant=false,
        range=true,
        format='',
        legendFormat="__auto",
        interval='$interval',
        datasource='$datasource'
      )) + { fieldConfig: { defaults: { max: 100, min: 0, decimals: 2, unit: "percentunit" } } },

      $.addTableExtended(
        datasource='$datasource',
        title='Gateway Information',
        gridPosition={ h: 9, w: 8, x: 0, y: 7 },
        color={ mode: 'thresholds' },
        options={
          footer: {
            fields: '',
            reducer: ['sum'],
            countRows: false,
            show: false,
          },
          sortBy: [],
          showHeader: true,
          cellHeight: "sm"
        },
        custom={ align: 'auto', cellOptions: { type: 'auto' }, inspect: false },
        thresholds={
          mode: 'absolute',
          steps: [
            { color: 'green' },
            { color: 'red', value: 80 }, 
          ],
        },
        overrides=[
          {
            "matcher": { "id": "byName", "options": "GW Version" },
            "properties": [{ "id": "custom.width", "value": 110}]
          },
          {
            "matcher": {"id": "byName", "options": "Count" },
            "properties": [{"id": "custom.width", "value": 80 }]
          },
          {
            "matcher": {"id": "byName", "options": "Address"},
            "properties": [{ "id": "custom.width", "value": 112 }]
          }
        ],
        pluginVersion='11.0.0'
      )
      .addTransformations([
        {
          id: 'organize',
          options: {
            "excludeByName": {
              "Time": true,
              "Value": true,
              "__name__": true,
              "instance": true,
              "job": true,
              "name": true,
              "port": true,
              "spdk_version": true
            },
            "includeByName": {},
            "indexByName": {
              "Time": 0,
              "Value": 11,
              "__name__": 2,
              "addr": 3,
              "group": 4,
              "hostname": 1,
              "instance": 5,
              "job": 6,
              "name": 7,
              "port": 8,
              "spdk_version": 9,
              "version": 10
            },
            "renameByName": {
              "Value": "",
              "addr": "Address",
              "group": "Group Name",
              "hostname": "Hostname",
              "job": "",
              "version": "GW Version"
            }
          },
        },
      ]).addTargets([
        $.addTargetSchema(
          expr='(ceph_nvmeof_gateway_info)',
          datasource='$datasource',
          format='table',
          exemplar=false,
          instant=true,
          interval='',
          legendFormat='__auto',
          range=false,
        ),
      ]),
    
      $.addBarGaugePanel(
        title='Top 5 Subsystems by Namespace',
        description='Show the subsystems by the count of namespaces they present to the client',
        datasource='${datasource}',
        gridPosition={ x: 8, y: 7, w: 5, h: 9 },
        unit='locale',
        thresholds={
          mode: 'absolute',
          steps: [
            { color: 'green' },
            { color: 'red', value: 80 }, 
          ],
        },
        // pluginVersion='11.0.0'  // TODO: will this work?
      )
      .addTargets([
        $.addTargetSchema(
          expr='topk(5, (count by(nqn) (count by(bdev_name, nqn) (ceph_nvmeof_subsystem_namespace_metadata))))', 
          datasource='${datasource}',
          exemplar=false,
          format='table',
          hide=false,
          legendFormat='__auto',
          range=false,
          instant=true
        ),
      ]) + { fieldConfig: { defaults: { color: { mode: 'palette-classic' }, thresholds: { mode: 'absolute', steps: [{ color: 'green', value: null }, { color: 'red', value: 80 }] }, min: 0 }, overrides: [{ matcher: { id: 'byType', unit: 'number' }, properties: [{ id: 'unit', value: 'decbytes' }] }] } }
      + { options: { orientation: 'horizontal', reduceOptions: { calcs: ['lastNotNull'], fields: '/^Value$/', limit: 5, values: true }, displayMode: 'basic',  maxVizHeight: 50, minVizHeight: 16, minVizWidth: 8, namePlacement: 'top', showUnfilled: true, sizing: "manual", "valueMode": "text" } },

      // TODO: add barchart 'Count of Namespace by ANA Group' 
     
      $.barChartPanel(
        title='Count of Namespace by ANA Group',
        description='Shows the distribution of namespaces by ANA group. Ideally, the namespaces should be evenly distributed across ANA groups.',
        datasource='$datasource',
        gridPos={ h: 9, w: 6, x: 13, y: 7 },
        axisCenteredZero=false,
        min=0,
        axisColorMode='text',
        axisLabel='Namespaces', // done
        axisPlacement='auto', // done
        // barAlignment=0,
        // drawStyle='line',
        fillOpacity=80, // done
        gradientMode='hue', // done
        // hideFrom
        // insertNulls
        // lineInterpolation='linear',
        lineWidth=1, // done
        // pointSize=5,
        scaleDistributionType='linear', // done
        // showPoints='auto',
        // spanNulls=false,
        // stackingGroup='A',
        // stackingMode='none',
        thresholdsStyleMode='off', // done
        unit='none',
        colorMode='thresholds',
        tooltip={
          "maxHeight": 600,
          "mode": "multi",
          "sort": "desc"
        },
        displayMode='list',
        placement='bottom',
        showLegend=false,
        thresholdsMode='absolute',
      )
      .addThresholds([
        { color: 'green', value: null },
      ])
      .addTargets(
        [
          $.addTargetSchema(
            expr='count by(anagrpid) ((count by(anagrpid,bdev_name) (ceph_nvmeof_subsystem_namespace_metadata)))',
            datasource='$datasource',
            instant=true,
            interval='10s',
            format='table',
            legendFormat='__auto',
            range=false,
          ),
        ]
      )
      .addOverrides(
        [
          {
            matcher: { id: 'byName', options: 'Value' },
            properties: [
              {
                id: 'custom.scaleDistribution',
                value: { type: "linear" },
              },
              {
                id: "custom.axisPlacement",
                value: "hidden"
              }
            ],
          },
          {
            matcher: { id: 'byName', options: 'anagrpid' },
            properties: [
              {
                id: 'custom.axisLabel',
                value: 'ANA Group ID',
              },
            ],
          },
        ]
      ),





      $.pieChartPanel(
        title='Clients Connected by Gateway',
        description='Even segments show clients are connected across the gateways in a uniform manner.',
        datasource='$datasource',
        gridPos={ x: 19, y: 7, w: 5, h: 9 },
        displayMode='table',
        placement='right',
        showLegend=true,
        displayLabels=[],
        tooltip={
          "maxHeight": 600,
          "mode": "single",
          "sort": "none"
        },
        pieType='donut',
        values=['value'],
        colorMode='auto',
        overrides=[],
        reduceOptions={
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        }
      )
      .addTargets([
        $.addTargetSchema(
          expr='count by(instance) (sum by(instance,host_nqn) (ceph_nvmeof_host_connection_state == 1))', 
          datasource='${datasource}',
          exemplar=false,
          format='time_series',
          hide=false,
          legendFormat='__auto',
          range=false,
          instant=true
        ) 
      ]) + { fieldConfig: { defaults: { color: { fixedColor: 'light-blue', mode: 'palette-classic' }, min: 0, unit: "locale", custom: { hideFrom: { legend: false, tooltip: false, viz: false } } } } },

      $.addRowSchema(collapse=false, showTitle=true, title='Performance') + { gridPos: { x: 0, y: 16, w: 24, h: 1 } },

      $.timeSeriesPanel(
        title='AVG Reactor CPU Usage by Gateway',
        datasource='$datasource',
        gridPosition={ h: 8, w: 8, x: 0, y: 17 },
        axisCenteredZero=false,
        axisColorMode='text',
        axisLabel='',
        axisPlacement='auto',
        barAlignment=0,
        drawStyle='line',
        fillOpacity=0,
        gradientMode='none',
        // hideFrom
        // insertNulls
        lineInterpolation='linear',
        lineWidth=1,
        pointSize=5,
        scaleDistributionType='linear',
        showPoints='auto',
        spanNulls=false,
        stackingGroup='A',
        stackingMode='none',
        thresholdsStyleMode='off',
        unit='percentunit',
        colorMode='palette-classic',
        tooltip={
          "maxHeight": 600,
          "mode": "multi",
          "sort": "desc"
        },
        displayMode='list',
        placement='bottom',
        showLegend=true,
        thresholdsMode='absolute',
      )
      .addThresholds([
        { color: 'green', value: null },
        { color: 'red', value: 80 },
      ])
      .addTargets(
        [
          $.addTargetSchema(
            expr='avg by(instance) (rate(ceph_nvmeof_reactor_seconds_total{mode=\"busy\"}[1m]))',
            datasource='$datasource',
            interval='10s',
            instant=false,
            format='',
            legendFormat='{{name}}',
            range=true,
          ),
        ]
      ),

      $.timeSeriesPanel(
        title='Reactor Threads CPU Usage : $gateway',
        // description='Reactor thread CPU busy comes from the SPDK',
        datasource='$datasource',
        gridPosition={ h: 8, w: 8, x: 8, y: 17 },
        axisCenteredZero=false,
        axisColorMode='text',
        axisLabel='',
        axisPlacement='auto',
        barAlignment=0,
        drawStyle='line',
        fillOpacity=0,
        gradientMode='none',
        // hideFrom
        // insertNulls
        lineInterpolation='linear',
        lineWidth=1,
        pointSize=5,
        scaleDistributionType='linear',
        showPoints='auto',
        spanNulls=false,
        stackingGroup='A',
        stackingMode='none',
        thresholdsStyleMode='off',
        unit='percentunit',
        colorMode='palette-classic',
        tooltip={
          "maxHeight": 600,
          "mode": "multi",
          "sort": "desc"
        },
        displayMode='list',
        placement='bottom',
        showLegend=true,
        thresholdsMode='absolute',
      )
      .addThresholds([
        { color: 'green', value: null },
        { color: 'red', value: 80 },
      ])
      .addTargets(
        [
          $.addTargetSchema(
            expr='rate(ceph_nvmeof_reactor_seconds_total{mode=\"busy\", instance=~\"$gateway.*\"}[1m])',
            datasource='$datasource',
            instant=false,
            interval='10s',
            format='',
            legendFormat='{{name}}',
            range=true,
          ),
        ]
      ),

      $.timeSeriesPanel(
        title='AVG I/O Latency',
        // description='I/O latency as determined by the SPDK ',
        datasource='$datasource',
        gridPosition={ h: 8, w: 8, x: 16, y: 17 },
        axisCenteredZero=false,
        axisColorMode='text',
        axisLabel='',
        axisPlacement='auto',
        barAlignment=0,
        drawStyle='line',
        fillOpacity=0,
        gradientMode='none',
        // hideFrom
        // insertNulls
        lineInterpolation='linear',
        lineWidth=1,
        pointSize=5,
        scaleDistributionType='linear',
        showPoints='auto',
        spanNulls=false,
        stackingGroup='A',
        stackingMode='none',
        thresholdsStyleMode='off',
        unit='s',
        colorMode='palette-classic',
        tooltip={
          "maxHeight": 600,
          "mode": "multi",
          "sort": "desc"
        },
        displayMode='list',
        placement='bottom',
        showLegend=true,
        thresholdsMode='absolute',
      )
      .addThresholds([
        { color: 'green', value: null },
        { color: 'red', value: 80 },
      ])
      .addTargets(
        [
          $.addTargetSchema(
            expr='avg((rate(ceph_nvmeof_bdev_read_seconds_total[30s]) / rate(ceph_nvmeof_bdev_reads_completed_total[30s])) > 0)',
            datasource='$datasource',
            // interval='$interval',
            instant=false,
            legendFormat='Reads',
            range=true,
            // refId="A",
          ),
          $.addTargetSchema(
            expr='avg((rate(ceph_nvmeof_bdev_write_seconds_total[30s]) / rate(ceph_nvmeof_bdev_writes_completed_total[30s])) > 0)',
            datasource='$datasource',
            // interval='$interval',
            instant=false,
            hide=false,
            legendFormat='Writes',
            range=true,
            // refId="B",
          ),
        ]
      ),

      $.timeSeriesPanel(
        title='IOPS by Gateway',
        // description='',
        datasource='$datasource',
        gridPosition={ h: 8, w: 8, x: 0, y: 25 },
        axisCenteredZero=false,
        axisColorMode='text',
        axisLabel='',
        axisPlacement='auto',
        barAlignment=0,
        drawStyle='line',
        fillOpacity=0,
        gradientMode='none',
        // hideFrom
        // insertNulls
        lineInterpolation='linear',
        lineWidth=1,
        pointSize=5,
        scaleDistributionType='linear',
        showPoints='auto',
        spanNulls=false,
        stackingGroup='A',
        stackingMode='none',
        thresholdsStyleMode='off',
        unit='locale',
        colorMode='palette-classic',
        tooltip={
          "maxHeight": 600,
          "mode": "multi",
          "sort": "desc"
        },
        displayMode='list',
        placement='bottom',
        showLegend=true,
        thresholdsMode='absolute',
      )
      .addThresholds([
        { color: 'green', value: null },
        { color: 'red', value: 80 },
      ])
      .addTargets(
        [
          $.addTargetSchema(
            expr='sum by(instance) (rate(ceph_nvmeof_bdev_reads_completed_total[1m]) + rate(ceph_nvmeof_bdev_writes_completed_total[1m]))',
            datasource='$datasource',
            interval='$interval',
            instant=false,
            legendFormat='__auto',
            range=true,
          ),
        ]
      ),

      $.timeSeriesPanel(
        title='IOPS by NVMe-oF Subsystem',
        // description='',
        datasource='$datasource',
        gridPosition={ h: 8, w: 8, x: 8, y: 25 },
        axisCenteredZero=false,
        axisColorMode='text',
        axisLabel='IOPS',
        axisPlacement='auto',
        barAlignment=0,
        drawStyle='line',
        fillOpacity=0,
        gradientMode='none',
        // hideFrom
        // insertNulls
        lineInterpolation='linear',
        lineWidth=1,
        pointSize=5,
        scaleDistributionType='linear',
        showPoints='auto',
        spanNulls=false,
        stackingGroup='A',
        stackingMode='none',
        thresholdsStyleMode='off',
        unit='locale',
        colorMode='palette-classic',
        tooltip={
          "maxHeight": 600,
          "mode": "multi",
          "sort": "desc"
        },
        displayMode='list',
        placement='bottom',
        showLegend=true,
        thresholdsMode='absolute',
      )
      .addThresholds([
        { color: 'green', value: null },
      ])
      .addTargets(
        [
          $.addTargetSchema(
            expr='\nsum by(nqn) ((rate(ceph_nvmeof_bdev_reads_completed_total[1m]) + rate(ceph_nvmeof_bdev_writes_completed_total[1m])) * on(instance,bdev_name) group_right ceph_nvmeof_subsystem_namespace_metadata)',
            datasource='$datasource',
            interval='$interval',
            instant=false,
            legendFormat='__auto',
            range=true,
            hide=false,
            // refId='E',
          ),
        ]
      ),

      $.timeSeriesPanel(
        title="TOP 5 - IOPS by device for '$subsystem'",
        // description='Shows the busiest rbd images (namespaces) within a given subsystem',
        datasource='$datasource',
        gridPosition={ h: 8, w: 8, x: 16, y: 25 },
        axisCenteredZero=false,
        axisColorMode='text',
        axisLabel='',
        axisPlacement='auto',
        barAlignment=0,
        drawStyle='line',
        fillOpacity=30,
        gradientMode='none',
        // hideFrom
        // insertNulls
        lineInterpolation='linear',
        lineWidth=1,
        pointSize=5,
        scaleDistributionType='linear',
        showPoints='auto',
        spanNulls=false,
        stackingGroup='A',
        stackingMode='normal',
        thresholdsStyleMode='off',
        unit='locale',
        colorMode='palette-classic',
        tooltip={
          "maxHeight": 600,
          "mode": "multi",
          "sort": "desc"
        },
        displayMode='list',
        placement='bottom',
        showLegend=true,
        thresholdsMode='absolute',
      )
      .addThresholds([
        { color: 'green', value: null },
        { color: 'red', value: 80 },
      ])
      .addTargets(
        [
          $.addTargetSchema(
            expr='topk(5, (sum by(pool_name, rbd_name) (((rate(ceph_nvmeof_bdev_reads_completed_total[1m]) + rate(ceph_nvmeof_bdev_writes_completed_total[1m])) * on(instance,bdev_name) group_right ceph_nvmeof_bdev_metadata) * on(instance, bdev_name) group_left(nqn) ceph_nvmeof_subsystem_namespace_metadata{nqn=\"$subsystem\"})))',
            datasource='$datasource',
            interval='$interval',
            instant=false,
            legendFormat='{{pool_name}}/{{rbd_name}}',
            range=true,
            hide=false,
            // refId="C",
          ),
        ]
      ),

      $.timeSeriesPanel(
        title='Throughput by Gateway',
        // description='',
        datasource='$datasource',
        gridPosition={ h: 8, w: 8, x: 0, y: 33 },
        axisCenteredZero=false,
        axisColorMode='text',
        axisLabel='',
        axisPlacement='auto',
        barAlignment=0,
        drawStyle='line',
        fillOpacity=30,
        gradientMode='none',
        // hideFrom
        // insertNulls
        lineInterpolation='linear',
        lineWidth=1,
        pointSize=5,
        scaleDistributionType='linear',
        showPoints='auto',
        spanNulls=false,
        stackingGroup='A',
        stackingMode='normal',
        thresholdsStyleMode='off',
        unit='binBps',
        colorMode='palette-classic',
        tooltip={
          "maxHeight": 600,
          "mode": "multi",
          "sort": "desc"
        },
        displayMode='list',
        placement='bottom',
        showLegend=true,
        thresholdsMode='absolute',
      )
      .addThresholds([
        { color: 'green', value: null },
        { color: 'red', value: 80 },
      ])
      .addTargets(
        [
          $.addTargetSchema(
            expr='sum by(instance) (rate(ceph_nvmeof_bdev_read_bytes_total[1m]) + rate(ceph_nvmeof_bdev_written_bytes_total[1m]))',
            datasource='$datasource',
            interval='$interval',
            instant=false,
            legendFormat='{{name}}',
            range=true,
            // refId='A',
          ),
        ]
      ),

      $.timeSeriesPanel(
        title='Throughput by NVMe-oF Subsystem',
        // description='',
        datasource='$datasource',
        gridPosition={ h: 8, w: 8, x: 8, y: 33 },
        axisCenteredZero=false,
        axisColorMode='text',
        axisLabel='Throughput',
        axisPlacement='auto',
        barAlignment=0,
        drawStyle='line',
        fillOpacity=10,
        gradientMode='none',
        // hideFrom
        // insertNulls
        lineInterpolation='linear',
        lineWidth=1,
        pointSize=5,
        scaleDistributionType='linear',
        showPoints='auto',
        spanNulls=false,
        stackingGroup='A',
        stackingMode='none',
        thresholdsStyleMode='off',
        unit='binBps',
        colorMode='palette-classic',
        tooltip={
          "maxHeight": 600,
          "mode": "multi",
          "sort": "desc"
        },
        displayMode='list',
        placement='bottom',
        showLegend=true,
        thresholdsMode='absolute',
      )
      .addThresholds([
        { color: 'green', value: null },
      ])
      .addTargets(
        [
          $.addTargetSchema(
            expr='sum by(pool_name,rbd_name) ((rate(ceph_nvmeof_bdev_reads_completed_total[1m]) * on(instance,bdev_name) group_right ceph_nvmeof_bdev_metadata) + (rate(ceph_nvmeof_bdev_writes_completed_total[1m]) * on(instance,bdev_name) group_right ceph_nvmeof_bdev_metadata))',
            datasource='$datasource',
            interval='$interval',
            instant=false,
            legendFormat='{{pool_name}}/{{rbd_name}}',
            range=true,
            hide=true,
            // refId='A'
          ),
          $.addTargetSchema(
            expr='sum by(pool_name,rbd_name) ((rate(ceph_nvmeof_bdev_read_bytes_total[1m]) * on(instance,bdev_name) group_right ceph_nvmeof_bdev_metadata) + (rate(ceph_nvmeof_bdev_written_bytes_total[1m]) * on(instance,bdev_name) group_right ceph_nvmeof_bdev_metadata))',
            datasource='$datasource',
            interval='$interval',
            instant=false,
            legendFormat='{{pool_name}}/{{rbd_name}}',
            range=true,
            hide=true,
            // refId='B',
          ),
          $.addTargetSchema(
            expr='rate(ceph_nvmeof_bdev_reads_completed_total[1m])',
            datasource='$datasource',
            interval='$interval',
            instant=false,
            legendFormat='__auto',
            range=true,
            hide=true,
            // refId='C',
          ),
          $.addTargetSchema(
            expr='count by(nqn,bdev_name) (count by(nqn,bdev_name) (ceph_nvmeof_subsystem_namespace_metadata))',
            datasource='$datasource',
            interval='$interval',
            instant=false,
            legendFormat='__auto',
            range=true,
            hide=true,
            // refId='D',
          ),
          $.addTargetSchema(
            expr='\nsum by(nqn) ((rate(ceph_nvmeof_bdev_read_bytes_total[1m]) + rate(ceph_nvmeof_bdev_written_bytes_total[1m])) * on(instance,bdev_name) group_right ceph_nvmeof_subsystem_namespace_metadata)',
            datasource='$datasource',
            interval='$interval',
            instant=false,
            legendFormat='__auto',
            range=true,
            hide=false,
            // refId='E',
          ),
        ]
      ),

      $.timeSeriesPanel(
        title="TOP 5 - Throughput by device for '$subsystem'",
        // description='Shows the rbd images (namespaces) with the highest throughput in a given subsystem',
        datasource='$datasource',
        gridPosition={ h: 8, w: 8, x: 16, y: 33 },
        axisCenteredZero=false,
        axisColorMode='text',
        axisLabel='',
        axisPlacement='auto',
        barAlignment=0,
        drawStyle='line',
        fillOpacity=30,
        gradientMode='none',
        // hideFrom
        // insertNulls
        lineInterpolation='linear',
        lineWidth=1,
        pointSize=5,
        scaleDistributionType='linear',
        showPoints='auto',
        spanNulls=false,
        stackingGroup='A',
        stackingMode='normal',
        thresholdsStyleMode='off',
        unit='binBps',
        colorMode='palette-classic',
        tooltip={
          "maxHeight": 600,
          "mode": "multi",
          "sort": "desc"
        },
        displayMode='list',
        placement='bottom',
        showLegend=true,
        thresholdsMode='absolute',
      )
      .addThresholds([
        { color: 'green', value: null },
        { color: 'red', value: 80 },
      ])
      .addTargets(
        [
          $.addTargetSchema(
            expr='topk(5, (sum by(pool_name, rbd_name) (((rate(ceph_nvmeof_bdev_read_bytes_total[1m]) + rate(ceph_nvmeof_bdev_written_bytes_total[1m])) * on(instance,bdev_name) group_right ceph_nvmeof_bdev_metadata) * on(instance, bdev_name) group_left(nqn) ceph_nvmeof_subsystem_namespace_metadata{nqn=\"$subsystem\"})))',
            datasource='$datasource',
            interval='$interval',
            instant=false,
            legendFormat='{{name}}',
            range=true,
            hide=false, 
            // refId='C'
          ),
        ]
      ),

    ]  //end panels
  ),
}

