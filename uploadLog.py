import os, uuid, sys
from azure.storage.blob import BlockBlobService, PublicAccess
from time import gmtime, strftime
from collections import OrderedDict
import re

name = "<insert your storage account name>"
key = "<insert your storage account key>"

local_path = os.path.expanduser("~/software/spinnakerTestUnit")

tests = OrderedDict()
tests["BakeAndDeployAPPGW"] = os.path.join(local_path, "bake_deploy_ag.txt")
tests["BakeAndRBDeployAPPGW"] = os.path.join(local_path, "bake_RB_deploy_ag.txt")
tests["BakeAndDeployLB"] = os.path.join(local_path, "bake_deploy_lb.txt")
tests["BakeAndRBDeployLB"] = os.path.join(local_path, "bake_RB_deploy_lb.txt")

failures = []
htmls = OrderedDict()
htmls["BakeAndDeployAPPGW"] = os.path.join(local_path, "azure_bake_and_deploy_ag.html")
htmls["BakeAndRBDeployAPPGW"] = os.path.join(local_path, "azure_bake_and_RB_deploy_ag.html")
htmls["BakeAndDeployLB"] = os.path.join(local_path, "azure_bake_and_deploy_lb.html")
htmls["BakeAndRBDeployLB"] = os.path.join(local_path, "azure_bake_and_RB_deploy_ag.html")

local_file = os.path.join(local_path, "tests.log")
local_abstract = os.path.join(local_path, "abstract.log")

cloud_file_prefix = "spinnakerTest-{date}".format(date=strftime("%Y/%m/%d", gmtime()))
cloud_file_name = "{prefix}.log".format(prefix=cloud_file_prefix)
cloud_abstract_name = "{prefix}-abstract.log".format(prefix=cloud_file_prefix)
container_name = "spinnakertestinglogs"

duration_pattern = re.compile(r"(?<= tests in )\d+\.?\d*s")

def merge():
    with open(local_file, 'w') as f:
        for t in tests:
            with open(tests[t], 'r') as tf:
                f.write("\n\n******** {date} - {tests} ********\n".format(date=strftime("%m/%d/%Y", gmtime()), tests=t))
                content = tf.read()
                f.write(content)

def mergeAbstract():
    with open(local_abstract, 'w') as f:
        f.write(strftime("Run Date:%Y-%m-%d\n", gmtime()))
        # f.write('Test Case Name\t\t\t\t| Result\t| Duration\n')
        for k in tests:
            with open(tests[k], 'r') as tf:
                contents = tf.read()
                duration = duration_pattern.findall(contents)[0]
                if "FAIL" in contents:
                    f.write(k+' FAIL '+ duration+'\n')
                    failures.append(k)
                else:
                    f.write(k+' SUCCESS '+ duration+'\n')

def upload():
    try:
        block_blob_service = BlockBlobService(
            account_name=name,
            account_key=key)
        #block_blob_service.create_container(container_name)
        block_blob_service.create_blob_from_path(container_name, cloud_file_name, local_file)
        block_blob_service.create_blob_from_path(container_name, cloud_abstract_name, local_abstract)
        for f in failures:
            block_blob_service.create_blob_from_path(container_name, 
                "{prefix}-{f}.html".format(prefix=cloud_file_prefix, f=f), 
                htmls[f])
        print("logs update to " + container_name + " successfully.")
        os.remove(local_file)
        # os.remove(local_abstract)

    except Exception as e:
        print(e)

if __name__ == '__main__':
    merge()
    mergeAbstract()
    upload()
