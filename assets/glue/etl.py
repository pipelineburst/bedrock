import sys
import os
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

args = getResolvedOptions(sys.argv, ['JOB_NAME'])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)
bucket_name = os.environ['CUSTOMER_BUCKET_NAME']

# Script generated for node Amazon S3
AmazonS3_node1716476673212 = glueContext.create_dynamic_frame.from_options(format_options={"quoteChar": "\"", "withHeader": True, "separator": ","}, connection_type="s3", format="csv", connection_options={"paths": [f"s3://{bucket_name}/data-set/"]}, transformation_ctx="AmazonS3_node1716476673212")

# Script generated for node Change Schema
ChangeSchema_node1716744216335 = ApplyMapping.apply(frame=AmazonS3_node1716476673212, mappings=[("4g_cell_name", "string", "4g_cell_name", "string"), ("date", "string", "date", "string"), ("4g_cell_availability", "string", "4g_cell_availability", "float"), ("4g_packet_cssr", "string", "4g_packet_cssr", "float"), ("4g_volte_erab_success_rate", "string", "4g_volte_erab_success_rate", "float"), ("4g_volte_erab_drop_rate", "string", "4g_volte_erab_drop_rate", "float"), ("4g_drop_packet", "string", "4g_drop_packet", "float"), ("4g_volte_traffic", "string", "4g_volte_traffic", "float"), ("4g_packet_data_traffic_gb", "string", "4g_packet_data_traffic_gb", "float"), ("4g_user_throughput_dl_mbps", "string", "4g_user_throughput_dl_mbps", "float"), ("4g_utilization", "string", "4g_utilization", "float"), ("vendor", "string", "vendor", "string"), ("city", "string", "city", "string"), ("cluster", "string", "cluster", "string"), ("district", "string", "district", "string"), ("governorate", "string", "governorate", "string"), ("region", "string", "region", "string"), ("x_coordinate", "string", "x_coordinate", "string"), ("y_coordinate", "string", "y_coordinate", "string"), ("fdd_tdd_technology", "string", "fdd_tdd_technology", "string")], transformation_ctx="ChangeSchema_node1716744216335")

# Script generated for node Amazon S3
AmazonS3_node1716476739276 = glueContext.getSink(path=f"s3://{bucket_name}/data-proc/", connection_type="s3", updateBehavior="UPDATE_IN_DATABASE", partitionKeys=["date"], enableUpdateCatalog=True, transformation_ctx="AmazonS3_node1716476739276")
AmazonS3_node1716476739276.setCatalogInfo(catalogDatabase="data_set_db",catalogTableName="data_proc")
AmazonS3_node1716476739276.setFormat("glueparquet", compression="snappy")
AmazonS3_node1716476739276.writeFrame(ChangeSchema_node1716744216335)
job.commit()