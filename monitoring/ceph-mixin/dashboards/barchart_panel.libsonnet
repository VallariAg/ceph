{
  /**
   * Creates a [Bar chart panel](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/bar-chart/).
   *
   * @name barchart_panel.new
   *
   * @param title (default `''`) Panel title.
   * @param description (default null) Panel description.
   */
  new(
    title='',
    description=null,
    pluginVersion='11.0.0',
    gridPos={},
    datasource='',
    colorMode='palette-classic',
    axisCenteredZero=false,
    axisColorMode='text',
    axisLabel='',
    axisPlacement='auto',
    fillOpacity=0,
    gradientMode='none',
    lineWidth=0,
    scaleDistributionType='linear',
    thresholdsStyleMode='off',
    decimals=null,
    thresholdsMode='absolute',
    unit='none',
    tooltip={},
    legend={},
    displayMode='list',
    placement='bottom',
    showLegend=true,
    min=null,
    scaleDistributionLog=null,
    sortBy=null,
    sortDesc=null,
    orientation='auto',
    showValue='auto',
    stacking='none',
    groupWidth=0.7,
    barWidth=0.97,
    barRadius=0,
    fullHighlight=false,
    xTickLabelRotation=0,
    xTickLabelSpacing=0
  ):: {
    title: title,
    type: 'barchart',
    [if description != null then 'description']: description,
    pluginVersion: pluginVersion,
    gridPos: gridPos,
    datasource: datasource,
    fieldConfig: {
      defaults: {
        color: { mode: colorMode },
        custom: {
          axisCenteredZero: axisCenteredZero,
          axisColorMode: axisColorMode,
          axisLabel: axisLabel,
          axisPlacement: axisPlacement,
          fillOpacity: fillOpacity,
          gradientMode: gradientMode,
          hideFrom: {
            legend: false,
            tooltip: false,
            viz: false,
          },
          lineWidth: lineWidth,
          scaleDistribution: {
            [if scaleDistributionLog != null then 'scaleDistributionLog']: scaleDistributionLog,
            type: scaleDistributionType,
          },
          thresholdsStyle: {
            mode: thresholdsStyleMode,
          },
        },
        [if decimals != null then 'decimals']: decimals,
        [if min != null then 'min']: min,
        thresholds: {
          mode: thresholdsMode,
          steps: [],
        },
        unit: unit,
      },
      overrides: [],
    },
    options: {
      orientation: orientation,
      showValue: showValue,
      stacking: stacking,
      groupWidth: groupWidth,
      barWidth: barWidth,
      barRadius: barRadius,
      fullHighlight: fullHighlight,
      xTickLabelRotation: xTickLabelRotation,
      xTickLabelSpacing: xTickLabelSpacing,
      legend: {
        calcs: [],
        displayMode: displayMode,
        placement: placement,
        showLegend: showLegend,
        [if sortBy != null then 'sortBy']: sortBy,
        [if sortDesc != null then 'sortDesc']: sortDesc,
      },
      tooltip: tooltip,
    },
    // Overrides
    addOverride(
      matcher=null,
      properties=null,
    ):: self {
      fieldConfig+: {
        overrides+: [
          {
            [if matcher != null then 'matcher']: matcher,
            [if properties != null then 'properties']: properties,
          },
        ],
      },
    },
    // thresholds
    addThreshold(step):: self {
      fieldConfig+: { defaults+: { thresholds+: { steps+: [step] } } },
    },
    addCalc(calc):: self {
      options+: { legend+: { calcs+: [calc] } },
    },
    _nextTarget:: 0,
    addTarget(target):: self {
      // automatically ref id in added targets.
      local nextTarget = super._nextTarget,
      _nextTarget: nextTarget + 1,
      targets+: [target { refId: std.char(std.codepoint('A') + nextTarget) }],
    },
    addTargets(targets):: std.foldl(function(p, t) p.addTarget(t), targets, self),
    addThresholds(steps):: std.foldl(function(p, s) p.addThreshold(s), steps, self),
    addCalcs(calcs):: std.foldl(function(p, t) p.addCalc(t), calcs, self),
    addOverrides(overrides):: std.foldl(function(p, o) p.addOverride(o.matcher, o.properties), overrides, self),
  },
}


