# Spinnaker test unit for azure based on citest

## Dependence
 * citest. see https://github.com/google/citest/
 * az. see https://docs.microsoft.com/cli/azure/install-azure-cli

## some error
    
 * In [citest\citest\gcp_testing\gcloud_agent.py](), method pty_fork_ssh(), and also in [citest\citest\gcp_testing\gce_util.py](), line 290, change argument async=False/True into asyn=False/True
 * We don't need google cloud, so delete [spinnaker_testing/gcs_pubsub_trigger_agent.py]() and [spinnaker_testing/google_scenario_support.py] ()and delete relevant code in [spinnaker_testing/\_\_init__.py]() and [spinnaker_testing/spinnaker_test_scenario.py]()

 * In [spinnaker_testing\gate.py](), method _maybe_export_stage_context(), line 132, convert err to string since sometimes err is None which cause string plus None error.