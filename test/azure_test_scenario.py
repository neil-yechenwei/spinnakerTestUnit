# Standard python modules.
import sys
import json

# citest modules.
import citest.base
import citest.azure_testing as az
import citest.json_contract as jc
import citest.json_predicate as jp
import citest.service_testing as st

# Spinnaker modules.
import spinnaker_testing as sk
import spinnaker_testing.gate as gate
ov_factory = jc.ObservationPredicateFactory()

class AzureTestScenario(sk.SpinnakerTestScenario):
    """Defines the scenario for the test
    This scenario defines the different test operations.
    """

    @classmethod
    def new_agent(cls, bindings):
        """Implements citest.service_testing.AgentTestScenario.new_agent."""
        agent = gate.new_agent(bindings)
        agent.default_max_wait_secs = 180
        return agent

    @classmethod
    def initArgumentParser(cls, parser, defaults=None):
        """Initialize command line argument parser.

        Args:
            parser: argparse.ArgumnetParser
        """

        super(AzureTestScenario, cls).initArgumentParser(
            parser, defaults=defaults)
        
        defaults = defaults or {}
        parser.add_argument(
            '--test_namespace', default='default',
            help='The namespace to manage within the tests.')

    def __init__(self, bindings, agent=None):
        """Constructor.
        Args:
        bindings: [dict] The data bindings to use to configure the scenario.
        agent: [GateAgent] The agent for invoking the test operations on Gate.
        """

        # to avoid error when citest call binding
        bindings['GCE_PROJECT'] = None
        bindings['GOOGLE_PRIMARY_MANAGED_PROJECT_ID'] = None

        super(AzureTestScenario, self).__init__(bindings, agent)
        bindings = self.bindings

        self.TEST_APP = bindings['TEST_APP']
        self.ACCOUNT = bindings['SPINNAKER_AZURE_ACCOUNT']
        self.__rg_name = bindings['TEST_AZURE_RESOURCE_GROUP']
        self.__rg_location = bindings['TEST_AZURE_RG_LOCATION']
        self.__subnet = bindings['TEST_AZURE_SUBNETS']
        self.__subscription_id = bindings['TEST_AZURE_SUBSCRIPTION_ID']
        self.__vnet_name = bindings['TEST_AZURE_VNET']
        self.__os_type = bindings['TEST_AZURE_OSTYPE']
        self.__base_os = bindings['TEST_AZURE_BASEOS']
        self.__stack = bindings['TEST_STACK']
        self.__detail = 'frontend'
        self.__sku = dict(
            name=bindings['TEST_AZURE_SKU']['NAME'],
            tier=bindings['TEST_AZURE_SKU']['TIER'],
            capacity=bindings['TEST_AZURE_SKU']['CAPACITY']
        )
        self.__full_lb_name = '{app}-{stack}-{detail}'.format(
            app=self.TEST_APP, stack=self.__stack,
            detail=self.__detail)

        assert len(self.__subnet) >= 2

    def create_app(self):
        """Creates OperationContract that creates a new Spinnaker Application."""
        return st.OperationContract(
            self.agent.make_create_app_operation(
                bindings=self.bindings, application=self.TEST_APP,
                account_name=self.ACCOUNT),
            contract=jc.Contract())

    def test_contract(self):
        """
        Create an OperationContract to trigger the builder.
        """
        builder = az.AzContractBuilder(self.az_observer)
        (builder.new_clause_builder(
            "Has Virtual Machine Scale Set", retryable_for_secs=30)
        .collect_resources(
            az_resource='vmss',
            command='list',
            args=['--resource-group', 
            '{app}-{rg}'.format(app=self.TEST_APP, rg=self.__rg_location)])
        .EXPECT(ov_factory.value_list_contains(
            jp.DICT_MATCHES({
                "name": jp.STR_EQ('{lb}-v002'.format(lb=self.__full_lb_name))
            })
        ))
        .EXPECT(ov_factory.value_list_contains(
            jp.DICT_MATCHES({
                "name": jp.STR_EQ('{lb}-v001'.format(lb=self.__full_lb_name))
            })
        ))
        .EXPECT(ov_factory.value_list_excludes(
            jp.DICT_MATCHES({
                "name": jp.STR_EQ('{lb}-v000'.format(lb=self.__full_lb_name))
            })
        )))
        return st.OperationContract(
            self.new_post_operation(
                title="test", data='', path='/'),
            contract=builder.build())

    def delete_app(self):
        """Creates OperationContract that deletes a new Spinnaker Application."""
        return st.OperationContract(
            self.agent.make_delete_app_operation(
                application=self.TEST_APP,
                account_name=self.ACCOUNT),
            contract=jc.Contract(),
            cleanup=self.delete_resource_group)

    def delete_resource_group(self, _unused_execution_context):
        """Deletes the Azure Resource Group created by this Spinnaker Application."""
        execution_context = citest.base.ExecutionContext()
        args = ['--name', 
                '{app}-{rg}'.format(app=self.TEST_APP, rg=self.__rg_location), 
                '--yes'] # wait until the Resource Group deleted
        cmd = self.az_observer.build_az_command_args('group', 'delete', args)
        self.az_observer.run(execution_context.eval(cmd))

    def create_load_balancer(self):
        """Create OperationContract that create a new Load Balancer

        To verify the operation, we just check that the spinnaker load balancer
        for the given application was created.
        """
        self.__lb_type = "Azure Load Balancer"
        healthyCheck = [{
            "probeName": "{lb}-probe".format(lb=self.__full_lb_name),
            "probeProtocol": "TCP",
            "probePort": "80",
            "probeInterval": 30,
            "unhealthyThreshold": 8,
            "timeout": 120
        }]
        rules = [{
            "ruleName": "{lb}-rule0".format(lb=self.__full_lb_name),
            "protocol": "TCP",
            "externalPort": 80,
            "backendPort": 80,
            "probeName": "{lb}-probe".format(lb=self.__full_lb_name),
            "persistence": "None",
            "idleTimeout": 4
        }]
        payload = self.agent.make_json_payload_from_kwargs(
            job=[{
                "stack": self.__stack,
                "detail": self.__detail,
                "credentials": self.ACCOUNT,
                "region": self.__rg_location,
                "cloudProvider": "azure",
                "vnet": None,
                "subnet": None,
                "probes": healthyCheck,
                "securityGroups": [],
                "loadBalancingRules": rules,
                "name": self.__full_lb_name,
                "selectedVnet": None,
                "vnetResourceGroup": None,
                "selectedSubnet": None,
                "type": "upsertLoadBalancer",
                "loadBalancerType": self.__lb_type,
                "appName": self.TEST_APP,
                "loadBalancerName": self.__full_lb_name,
                "user": "[anonymous]"
            }],
            description="Test - Create load balancer: {lb}".format(
                lb=self.__full_lb_name),
            application=self.TEST_APP)

        builder = az.AzContractBuilder(self.az_observer)
        (builder.new_clause_builder(
            'Load Balancer Created', retryable_for_secs=30)
        .collect_resources(
            az_resource='network',
            command='lb',
            args=['list', '--resource-group',
            '{app}-{rg}'.format(app=self.TEST_APP, rg=self.__rg_location)])
        .EXPECT(ov_factory.value_list_contains(
            jp.DICT_MATCHES({
                'name': jp.STR_EQ(self.__full_lb_name),
                'location': jp.STR_EQ(self.__rg_location)
            }))))

        return st.OperationContract(
            self.new_post_operation(
                title="create_load_balancer", data=payload,
                path=('applications/{app}/tasks').format(app=self.TEST_APP),
                max_wait_secs=2400),
            contract=builder.build())


    def create_application_gateway(self):
        """Create OperationContract that create a new Application gateway

        To verify the operation, we just check that the spinnaker load balancer
        for the given application was created.
        """
        self.__lb_type = "Azure Application Gateway"
        healthyCheck = [{
            "probeName": "{lb}-probe".format(lb=self.__full_lb_name),
            "probeProtocol": "HTTP",
            "probePort": "80",
            "probePath": "/",
            "probeInterval": 30,
            "unhealthyThreshold": 8,
            "timeout": 120
        }]
        rules = [{
            "ruleName": "{lb}-rule0".format(lb=self.__full_lb_name),
            "protocol": "HTTP",
            "externalPort": 80,
            "backendPort": 80,
            "probeName": "{lb}-probe".format(lb=self.__full_lb_name),
            "persistence": "None",
            "idleTimeout": 4
        }]
        subnets = [{
            "account": self.ACCOUNT,
            "addressPrefix": self.__subnet[0]['ADDRESS'],
            "device": [],
            "id": '/subscriptions/{id}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{vnet}/subnets/{name}'.format(
                id=self.__subscription_id, rg=self.__rg_name,
                vnet=self.__vnet_name, name=self.__subnet[0]['NAME']
            ),
            "name": self.__subnet[0]['NAME'],
            "purpose": 'TBD',
            "region": self.__rg_location,
            "type": 'azure',
            "vnet": self.__vnet_name
        }, {
            "account": self.ACCOUNT,
            "addressPrefix": self.__subnet[1]['ADDRESS'],
            "device": [],
            "id": '/subscriptions/{id}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{vnet}/subnets/{name}'.format(
                id=self.__subscription_id, rg=self.__rg_name,
                vnet=self.__vnet_name, name=self.__subnet[1]['NAME']
            ),
            "name": self.__subnet[1]['NAME'],
            "purpose": 'TBD',
            "region": self.__rg_location,
            "type": 'azure',
            "vnet": self.__vnet_name
        }]
        vnet = {
            "account": self.ACCOUNT,
            "cloudProvider": "azure",
            "id": self.__vnet_name,
            "name": self.__vnet_name,
            "region": self.__rg_location,
            "resourceGroup": self.__rg_name,
            "subnets": subnets
        }

        payload = self.agent.make_json_payload_from_kwargs(
            job=[{
                "stack": self.__stack,
                "detail": self.__detail,
                "credentials": self.ACCOUNT,
                "region": self.__rg_location,
                "cloudProvider": "azure",
                "vnet": self.__vnet_name,
                "subnet": self.__subnet[1]['NAME'],
                "probes": healthyCheck,
                "securityGroups": [],
                "loadBalancingRules": rules,
                "name": self.__full_lb_name,
                "selectedVnet": vnet,
                "vnetResourceGroup": self.__rg_name,
                "selectedSubnet": subnets[1],
                "type": "upsertLoadBalancer",
                "loadBalancerType": self.__lb_type,
                "appName": self.TEST_APP,
                "loadBalancerName": self.__full_lb_name,
                "user": "[anonymous]"
            }],
            description="Test - Create application gateway: {lb}".format(
                lb=self.__full_lb_name),
            application=self.TEST_APP)

        builder = az.AzContractBuilder(self.az_observer)
        (builder.new_clause_builder(
            'Application Gateway Created', retryable_for_secs=30)
        .collect_resources(
            az_resource='network',
            command='application-gateway',
            args=['list', '--resource-group',
            '{app}-{rg}'.format(app=self.TEST_APP, rg=self.__rg_location)])
        .EXPECT(ov_factory.value_list_contains(
            jp.DICT_MATCHES({
                'name': jp.STR_EQ(self.__full_lb_name),
                'tags': jp.DICT_MATCHES({
                    'vnet': jp.STR_EQ(self.__vnet_name),
                    'subnet': jp.STR_EQ(self.__subnet[1]['NAME'])
                })
            }))))

        return st.OperationContract(
            self.new_post_operation(
                title="create_application_gateway", data=payload,
                path=('applications/{app}/tasks').format(app=self.TEST_APP),
                max_wait_secs=3600),
            contract=builder.build())
    
    def delete_load_balancer(self):
        """Create OperationContract that delete the Load Balancer

        To verify the operation, we just check that the spinnaker load balancer
        for the given application was deleted.
        """

        payload = self.agent.make_json_payload_from_kwargs(
            job=[{
                "cloudProvider": "azure",
                "loadBalancerName": self.__full_lb_name,
                "loadBalancerType": self.__lb_type,
                "credentials": self.ACCOUNT,
                "region": self.__rg_location,
                "appName": self.TEST_APP,
                "type": "deleteLoadBalancer",
                "user": "[anonymous]"
            }],
            description="Test - Delete load balancer: {lb}".format(
                lb=self.__full_lb_name),
            application=self.TEST_APP)

        builder = az.AzContractBuilder(self.az_observer)
        (builder.new_clause_builder(
            'Load Balancer Deleted', retryable_for_secs=30)
        .collect_resources(
            az_resource='network',
            command='application-gateway',
            args=['list', '--resource-group',
            '{app}-{rg}'.format(app=self.TEST_APP, rg=self.__rg_location)])
        # expected no lb
        .EXPECT(ov_factory.error_list_contains(
            jp.ExceptionMatchesPredicate(
                klass=st.CliAgentRunError,
                regex=r'(?:.* operation: Cannot find .*)|(?:.*\(.*could not be found.\).*)')))
        # or no target lb
        .OR(ov_factory.value_list_excludes(
            jp.DICT_MATCHES({
                "name": jp.STR_EQ(self.__full_lb_name)
            })
        )))

        return st.OperationContract(
            self.new_post_operation(
                title='delete_load_balancer', data=payload,
                path=('applications/{app}/tasks').format(app=self.TEST_APP),
                max_wait_secs=1800),
            contract=builder.build())

    def make_bake_stage(self, providerType, package="", requisiteStage=[], **kwargs):
        stage  ={
            "refId": "BAKE",
            "requisiteStageRefIds": requisiteStage,
            "type": "bake",
            "name": "Bake",
            "cloudProviderType": providerType,
            "extendedAttributes": {},
            "regions": [self.__rg_location],
            "user": "[anonymous]",
            "osType": self.__os_type,
            "baseOs": self.__base_os,
            "baseLabel": "release",
            "package": package,
        }
        stage.update(kwargs)
        return stage

    def make_empty_image(self):
        image = {
            "imageName": "",
            "isCustom": "true",
            "publisher": "",
            "offer": "",
            "sku": "",
            "version": "",
            "region": self.__rg_location,
            "uri": "",
            "ostype": ""
        }
        return image

    def make_azure_RB_deploy_stage(self, requisiteStage=[], **kwargs):
        clusters = [{
            "name": self.__full_lb_name,
            "cloudProvider": "azure",
            "application": self.TEST_APP,
            "stack": self.__stack,
            "strategy": "redblack",
            "rollback": {
                "onFailure": False,
            },
            "scaleDown": False,
            "maxRemainingAsgs": 2,
            "delayBeforeDisableSec": 0,
            "delayBeforeScaleDownSec": 0,
            "allowDeleteActive": True,
            "allowScaleDownActive": True,
            "detail": self.__detail,
            "freeFormDetails": self.__detail,
            "account": self.ACCOUNT,
            "selectedProvider": "azure",
            "vnet": self.__vnet_name,
            "vnetResourceGroup": self.__rg_name,
            "subnet": self.__subnet[0]['NAME'],
            "useSourceCapacity": False,
            "capacity": {
                "min": 1,
                "max": 1
            },
            "region": self.__rg_location,
            "loadBalancerName": self.__full_lb_name,
            "loadBalancerType": self.__lb_type,
            "user": "[anonymous]",
            "upgradePolicy": "Manual",
            "type": "createServerGroup",
            "image": self.make_empty_image(),
            "sku": self.__sku,
            "instanceTags": {},
            "viewState":{
                "instanceProfile": "custom",
                "allImageSelection": None,
                "useAllImageSelection": False,
                "useSimpleCapacity": True,
                "usePreferredZones": True,
                "mode": "createPipeline",
                "disableStrategySelection": False,
                "loadBalancersConfigured": True,
                "networkSettingsConfigured": True,
                "securityGroupsConfigured": True,
                "disableImageSelection": True,
                "showImageSourceSelector": True,
                "expectedArtifacts": [],
                "imageId": None,
                "readOnlyFields": {},
                "submitButtonLabel": "Add",
                "hideClusterNamePreview": False,
                "templatingEnabled": True
            },
            "osConfig": {
                "customData": None
            },
            "customScriptsSettings": {
                "fileUris": None,
                "commandToExecute": ""
            },
            "zonesEnabled": False,
            "zones": [],
            "enableInboundNAT": False,
            "instanceType": self.__sku['name'],
            "interestingHealthProviderNames": []
        }]

        stage = {
            "refId": "DEPLOY",
            "requisiteStageRefIds": requisiteStage,
            "type": "deploy",
            "name": "Deploy",
            "clusters": clusters
        }
        stage.update(kwargs)
        return stage


    def make_azure_deploy_stage(self, requisiteStage=[], **kwargs):
        clusters = [{
            "name": self.__full_lb_name,
            "cloudProvider": "azure",
            "application": self.TEST_APP,
            "stack": self.__stack,
            "strategy": "",
            "rollback": {
                "onFailure": None,
            },
            "allowDeleteActive": None,
            "allowScaleDownActive": None,
            "detail": self.__detail,
            "freeFormDetails": self.__detail,
            "account": self.ACCOUNT,
            "selectedProvider": "azure",
            "vnet": self.__vnet_name,
            "vnetResourceGroup": self.__rg_name,
            "subnet": self.__subnet[0]['NAME'],
            "useSourceCapacity": False,
            "capacity": {
                "min": 1,
                "max": 1
            },
            "region": self.__rg_location,
            "loadBalancerName": self.__full_lb_name,
            "loadBalancerType": self.__lb_type,
            "user": "[anonymous]",
            "upgradePolicy": "Manual",
            "type": "createServerGroup",
            "image": self.make_empty_image(),
            "sku": self.__sku,
            "instanceTags": {},
            "viewState":{
                "instanceProfile": "custom",
                "allImageSelection": None,
                "useAllImageSelection": False,
                "useSimpleCapacity": True,
                "usePreferredZones": True,
                "mode": "createPipeline",
                "disableStrategySelection": True,
                "loadBalancersConfigured": True,
                "networkSettingsConfigured": True,
                "securityGroupsConfigured": True,
                "disableImageSelection": True,
                "showImageSourceSelector": True,
                "expectedArtifacts": [],
                "imageId": None,
                "readOnlyFields": {},
                "submitButtonLabel": "Add",
                "hideClusterNamePreview": False,
                "templatingEnabled": True
            },
            "osConfig": {
                "customData": None
            },
            "customScriptsSettings": {
                "fileUris": None,
                "commandToExecute": ""
            },
            "zonesEnabled": False,
            "zones": [],
            "enableInboundNAT": False,
            "instanceType": self.__sku['name'],
            "interestingHealthProviderNames": []
        }]
   
        stage = {
            "refId": "DEPLOY",
            "requisiteStageRefIds": requisiteStage,
            "type": "deploy",
            "name": "Deploy",
            "clusters": clusters
        }
        stage.update(kwargs)
        return stage

    def make_azure_disable_group_stage(self, requisiteStage=[], **kwargs):
        moniker = {
            "app": self.TEST_APP,
            "cluster": self.__full_lb_name,
            "detail": self.__detail,
            "stack": self.__stack
        }
        stage = {
            "cloudProvider": "azure",
            "cloudProviderType": "azure",
            "cluster": self.__full_lb_name,
            "credentials": self.ACCOUNT,
            "moniker": moniker,
            "name": "Disable Server Group",
            "refId": "DISABLE",
            "regions": [self.__rg_location],
            "requisiteStageRefIds": requisiteStage,
            "target": "current_asg_dynamic",
            "type": "disableServerGroup"
		}
        stage.update(kwargs)
        return stage

    def make_azure_destroy_group_stage(self, requisiteStage=[], **kwargs):
        moniker = {
            "app": self.TEST_APP,
            "cluster": self.__full_lb_name,
            "detail": self.__detail,
            "stack": self.__stack
        }
        stage = {
            "cloudProvider": "azure",
            "cloudProviderType": "azure",
            "cluster": self.__full_lb_name,
            "credentials": self.ACCOUNT,
            "interestingHealthProviderNames": [],
            "moniker": moniker,
            "name": "Destroy Server Group",
            "refId": "DESTROY",
            "regions": [self.__rg_location],
            "requisiteStageRefIds": requisiteStage,
            "target": "current_asg_dynamic",
            "type": "destroyServerGroup"
        }
        stage.update(kwargs)
        return stage

    def create_bake_and_deploy_pipeline(self, strategy=""):
        """Create OperationContract that create the bake and deploy pipeline

        To verify the operation, we just check that the bake and deploy pipeline
        with the default name was created.
        """

        name = 'BakeAndDeploy'
        self.bake_pipeline_id = name
        bake_stage = self.make_bake_stage(providerType='azure')
        if strategy == "redblack":
            deploy_stage = self.make_azure_RB_deploy_stage(requisiteStage=['BAKE'])
        else:
            deploy_stage = self.make_azure_deploy_stage(requisiteStage=['BAKE'])

        pipeline_spec = dict(
            stages=[bake_stage, deploy_stage],
            stageCounter=2,
            triggers=[],
            limitConcurrent=True,
            keepWaitingPipelines=False,
            name=name,
            application=self.TEST_APP
        )

        payload = self.agent.make_json_payload_from_kwargs(**pipeline_spec)

        builder = st.HttpContractBuilder(self.agent)
        (builder.new_clause_builder('Has Pipeline')
            .get_url_path(
                'applications/{app}/pipelineConfigs'.format(app=self.TEST_APP))
            .contains_path_value(None, {"name": name})
        )

        return st.OperationContract(
            self.new_post_operation(
                title="create bake pipeline", data=payload, path='pipelines',
                status_class=st.SynchronousHttpOperationStatus),
            contract=builder.build())

    def create_disable_and_destroy_pipeline(self):
        """Create OperationContract that create the disable and destroy pipeline

        To verify the operation, we just check that the disable and destroy pipeline
        with the default name was created.
        """

        name = 'DisableAndDestroy'
        self.destroy_pipeline_id = name
        disable_stage = self.make_azure_disable_group_stage()
        destroy_stage = self.make_azure_destroy_group_stage(requisiteStage=["DISABLE"])

        pipeline_spec = dict(
            stages=[disable_stage, destroy_stage],
            stageCounter=2,
            triggers=[],
            limitConcurrent=True,
            keepWaitingPipelines=False,
            name=name,
            application=self.TEST_APP
        )

        payload = self.agent.make_json_payload_from_kwargs(**pipeline_spec)

        builder = st.HttpContractBuilder(self.agent)
        (builder.new_clause_builder('Has Pipeline')
            .get_url_path(
                'applications/{app}/pipelineConfigs'.format(app=self.TEST_APP))
            .contains_path_value(None, {"name": name})
        )

        return st.OperationContract(
            self.new_post_operation(
                title="create destroy pipeline", data=payload, path='pipelines',
                status_class=st.SynchronousHttpOperationStatus),
            contract=builder.build())
    
    def delete_pipeline(self, pipeline_id):
        """Create OperationContract that delete target pipeline
        Args:
            pipeline_id: [str] The name of the pipeline to be delete

        To verify the operation, we just check that the pipeline
        with the given name was deleted.
        """

        builder = st.HttpContractBuilder(self.agent)
        (builder.new_clause_builder('Has Pipeline', retryable_for_secs=5)
            .get_url_path(
                'applications/{app}/pipelineConfigs'.format(app=self.TEST_APP))
            .excludes_path_value('name', pipeline_id))

        return st.OperationContract(
            self.new_delete_operation(
                title="delete pipeline", data="",
                path=('pipelines/{app}/{pl}'.format(
                    app=self.TEST_APP,
                    pl=pipeline_id
                )),
                status_class=st.SynchronousHttpOperationStatus),
            contract=builder.build())

    def trigger_bake_and_deploy_pipeline(self, sg_id='v000'):
        """Create OperationContract that manually trigger the bake and deploy pipeline
        This create a new server group below the given load balancer.

        To verify the operation, we check that the spinnaker server group
        for the given load balancer was created in correct size.
        """

        pipeline_id = self.bake_pipeline_id
        payload = self.agent.make_json_payload_from_kwargs(
            job=[{
                "dryRun": False,
                "type": "manual",
                "user": "[anonymous]"
            }],
            description="Test - begin bake and deploy: {pl}".format(
                pl=pipeline_id),
            application=self.TEST_APP)

        builder = az.AzContractBuilder(self.az_observer)
        (builder.new_clause_builder(
            "Has Virtual Machine Scale Set", retryable_for_secs=30)
        .collect_resources(
            az_resource='vmss',
            command='list',
            args=['--resource-group', 
            '{app}-{rg}'.format(app=self.TEST_APP, rg=self.__rg_location)])
        .EXPECT(ov_factory.value_list_contains(
            jp.DICT_MATCHES({
                "name": jp.STR_EQ('{lb}-{sg}'.format(lb=self.__full_lb_name, sg=sg_id)),
                "sku": jp.DICT_MATCHES({
                    "name": jp.STR_EQ(self.__sku['name']),
                    "tier": jp.STR_EQ(self.__sku['tier']),
                    "capacity": jp.NUM_EQ(self.__sku['capacity'])
                })
            })
        )))

        return st.OperationContract(
            self.new_post_operation(
                title='bake and deploy', data=payload,
                # TODO: cannot use v2 url: pipelines/v2/{app}/{pl}
                path='pipelines/{app}/{pl}'.format(
                    app=self.TEST_APP, pl=pipeline_id),
                max_wait_secs=3600),
            contract=builder.build())

    def trigger_bake_and_RB_deploy_pipeline(self):
        """Create OperationContract that manually trigger the bake and deploy pipeline
        This create a new server group below the given load balancer and destroy the eldest one

        To verify the operation, we check that the spinnaker server groups
        for the given load balancer was created in correct size.
        """

        pipeline_id = self.bake_pipeline_id
        payload = self.agent.make_json_payload_from_kwargs(
            job=[{
                "dryRun": False,
                "type": "manual",
                "user": "[anonymous]"
            }],
            description="Test - begin bake and deploy: {pl}".format(
                pl=pipeline_id),
            application=self.TEST_APP)

        # Assuming the max remaining Asgs is 2
        builder = az.AzContractBuilder(self.az_observer)
        (builder.new_clause_builder(
            "Has Virtual Machine Scale Set", retryable_for_secs=30)
        .collect_resources(
            az_resource='vmss',
            command='list',
            args=['--resource-group', 
            '{app}-{rg}'.format(app=self.TEST_APP, rg=self.__rg_location)])
        .EXPECT(ov_factory.value_list_contains(
            jp.DICT_MATCHES({
                "name": jp.STR_EQ('{lb}-v002'.format(lb=self.__full_lb_name))
            })
        ))
        .EXPECT(ov_factory.value_list_contains(
            jp.DICT_MATCHES({
                "name": jp.STR_EQ('{lb}-v001'.format(lb=self.__full_lb_name))
            })
        ))
        .EXPECT(ov_factory.value_list_excludes(
            jp.DICT_MATCHES({
                "name": jp.STR_EQ('{lb}-v000'.format(lb=self.__full_lb_name))
            })
        )))

        return st.OperationContract(
            self.new_post_operation(
                title='bake and deploy', data=payload,
                # TODO: cannot use v2 url: pipelines/v2/{app}/{pl}
                path='pipelines/{app}/{pl}'.format(
                    app=self.TEST_APP, pl=pipeline_id),
                max_wait_secs=7200),
            contract=builder.build())

    def trigger_disable_and_destroy(self, sg_id='v000'):
        """Create OperationContract that manually trigger the disable and destroy pipeline

        To verify the operation, we just check that the spinnaker server group
        for the given load balancer was deleted.
        """

        pipeline_id = self.destroy_pipeline_id
        payload = self.agent.make_json_payload_from_kwargs(
            job=[{
                "dryRun": False,
                "type": "manual",
                "user": "[anonymous]"
            }],
            description="Test - begin disable and destroy server group: {pl}".format(
                pl=pipeline_id),
            application=self.TEST_APP)

        builder = az.AzContractBuilder(self.az_observer)
        (builder.new_clause_builder(
            "Has No Virtual Machine Scale Set", retryable_for_secs=30)
        .collect_resources(
            az_resource='vmss',
            command='list',
            args=['--resource-group', 
            '{app}-{rg}'.format(app=self.TEST_APP, rg=self.__rg_location)])
        .EXPECT(ov_factory.error_list_contains(
            jp.ExceptionMatchesPredicate(
                klass=st.CliAgentRunError,
                regex=r'(?:.* operation: Cannot find .*)|(?:.*\(.*could not be found.\).*)')))
        .OR(ov_factory.value_list_excludes(
            jp.DICT_MATCHES({
                "name": jp.STR_EQ('{lb}-{sg}'.format(lb=self.__full_lb_name, sg=sg_id))
            })
        )))

        return st.OperationContract(
            self.new_post_operation(
                title='disable and destroy', data=payload,
                # TODO: cannot use v2 url: pipelines/v2/{app}/{pl}
                path='pipelines/{app}/{pl}'.format(
                    app=self.TEST_APP, pl=pipeline_id),
                max_wait_secs=3600),
            contract=builder.build())
