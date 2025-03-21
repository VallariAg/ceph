{
  grafanaDashboards+::
    (import 'dashboards/cephfs.libsonnet') +
    (import 'dashboards/host.libsonnet') +
    (import 'dashboards/osd.libsonnet') +
    (import 'dashboards/pool.libsonnet') +
    (import 'dashboards/rbd.libsonnet') +
    (import 'dashboards/rgw.libsonnet') +
    (import 'dashboards/ceph-cluster.libsonnet') +
    (import 'dashboards/rgw-s3-analytics.libsonnet') +
    (import 'dashboards/multi-cluster.libsonnet') +
    (import 'dashboards/ceph-nvmeof-gateways.libsonnet') +
    (import 'dashboards/test.libsonnet') +
    { _config:: $._config },
}
