# Standard python modules.
import sys
import json

# citest modules.
import citest.base
import citest.service_testing as st

# Spinnaker modules.
from azure_test_scenario import AzureTestScenario

class AzureTest(st.AgentTestCase):
    """The test fixture for the AzureBakeAndDeployTest.

    This is implemented using citest OperationContract instances that are
    created by the AzureBakeAndDeployTestScenario.
    """
    @property
    def scenario(self):
        return citest.base.TestRunner.global_runner().get_shared_data(
            AzureTestScenario)

    def test_a_create_app(self):
        self.run_test_case(self.scenario.create_app())

    def test_b_create_load_balancer(self):
        self.run_test_case(self.scenario.create_load_balancer())

    def test_c1_create_bake_and_deploy_pipeline(self):
        self.run_test_case(self.scenario.create_bake_and_deploy_pipeline())

    def test_c2_create_disable_and_destroy_pipeline(self):
        self.run_test_case(self.scenario.create_disable_and_destroy_pipeline())

    def test_d_trigger_bake_and_deploy_pipeline(self):
        self.run_test_case(self.scenario.trigger_bake_and_deploy_pipeline())

    def test_w_trigger_disable_and_destroy_pipeline(self):
        self.run_test_case(self.scenario.trigger_disable_and_destroy())

    def test_x1_delete_bake_and_deploy_pipeline(self):
        self.run_test_case(self.scenario.delete_pipeline(
            self.scenario.bake_pipeline_id
        ))

    def test_x2_delete_disable_and_destroy_pipeline(self):
        self.run_test_case(self.scenario.delete_pipeline(
            self.scenario.destroy_pipeline_id
        ))

    def test_y_delete_load_balancer(self):
        self.run_test_case(self.scenario.delete_load_balancer(),
                            max_retries=1)

    def test_z_delete_app(self):
        self.run_test_case(self.scenario.delete_app(),
                            retry_interval_secs=8, max_retries=8)                    


def main():
    """Implements the main method running this smoke test."""

    with open('./azure_config.json', 'r', encoding='utf-8') as f:
        defaults = json.load(f)
        f.close()
    defaults['TEST_APP'] += "p0lb" + AzureTestScenario.DEFAULT_TEST_ID

    return citest.base.TestRunner.main(
        parser_inits=[AzureTestScenario.initArgumentParser],
        default_binding_overrides=defaults,
        test_case_list=[AzureTest])

if __name__ == '__main__':
    sys.exit(main())
