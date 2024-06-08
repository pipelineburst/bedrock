import sys
import os
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

# Initiate the spark session context
args = getResolvedOptions(sys.argv, ['JOB_NAME'])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Assign the bucket name
bucket_name = os.environ['CUSTOMER_BUCKET_NAME']

# Load the data set from Amazon S3 into a dynamic data frame
load_data = glueContext.create_dynamic_frame.from_options(format_options={"quoteChar": "\"", "withHeader": True, "separator": ","}, connection_type="s3", format="csv", connection_options={"paths": [f"s3://{bucket_name}/data-set/"]}, transformation_ctx="load_data")

# Convert the dynamic frame to a data frame
df = load_data.toDF()
print(df.dtypes)
df.show()

# Create a user defined function and define a lambda to clean and remove characters such as '%' and ' '
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType
chop_f = udf(lambda x: x.replace('%', '').replace(' ', ''), StringType())
clean_df = df.withColumn("4G Packet CSSR", chop_f(df["4G Packet CSSR"])).withColumn("4G Cell Availability", chop_f(df["4G Cell Availability"])).withColumn("4G Volte eRAB Success Rate", chop_f(df["4G Volte eRAB Success Rate"])).withColumn("4G Volte eRAB Drop Rate", chop_f(df["4G Volte eRAB Drop Rate"])).withColumn("4G Drop Packet", chop_f(df["4G Drop Packet"])).withColumn("4G Utilization", chop_f(df["4G Utilization"]))
clean_df.show()

# Convert the data frame back to a dynamic frame
from awsglue.dynamicframe import DynamicFrame
df_tmp = DynamicFrame.fromDF(clean_df, glueContext)

# Now we can update the schema of the dynamic frame and typecast the columns
schema_update = ApplyMapping.apply(frame=df_tmp, mappings=[("4g cell name", "string", "4g_cell_name", "string"), ("date", "string", "date", "string"), ("4g cell availability", "string", "4g_cell_availability", "float"), ("4g packet cssr", "string", "4g_packet_cssr", "float"), ("4g volte erab success rate", "string", "4g_volte_erab_success_rate", "float"), ("4g volte erab drop rate", "string", "4g_volte_erab_drop_rate", "float"), ("4g drop packet", "string", "4g_drop_packet", "float"), ("4g volte traffic", "string", "4g_volte_traffic", "float"), ("4g packet data traffic gb", "string", "4g_packet_data_traffic_gb", "float"), ("4g_user_throughput_dl_mbps", "string", "4g_user_throughput_dl_mbps", "float"), ("4g utilization", "string", "4g_utilization", "float"), ("vendor", "string", "vendor", "string"), ("city", "string", "city", "string"), ("cluster", "string", "cluster", "string"), ("district", "string", "district", "string"), ("governorate", "string", "governorate", "string"), ("region", "string", "region", "string"), ("x coordinate", "string", "x_coordinate", "string"), ("y coordinate", "string", "y_coordinate", "string"), ("fdd tdd technology", "string", "fdd_tdd_technology", "string")], transformation_ctx="schema_update")

# Write the data back to Amazon S3 in parquet format
write_data = glueContext.getSink(path=f"s3://{bucket_name}/data-proc/", connection_type="s3", updateBehavior="UPDATE_IN_DATABASE", partitionKeys=["date"], enableUpdateCatalog=True, transformation_ctx="write_data")
write_data.setCatalogInfo(catalogDatabase="data_set_db",catalogTableName="data_proc")
write_data.setFormat("glueparquet", compression="snappy")
write_data.writeFrame(schema_update)
job.commit()

### This is a AWS Glue Studio example 
### Generated with the visual ETL console.
# # Load the data set from Amazon S3
# AmazonS3_node1716476673212 = glueContext.create_dynamic_frame.from_options(format_options={"quoteChar": "\"", "withHeader": True, "separator": ","}, connection_type="s3", format="csv", connection_options={"paths": [f"s3://{bucket_name}/data-set/"]}, transformation_ctx="AmazonS3_node1716476673212")

# # Update the schema
# ChangeSchema_node1716744216335 = ApplyMapping.apply(frame=AmazonS3_node1716476673212, mappings=[("4g_cell_name", "string", "4g_cell_name", "string"), ("date", "string", "date", "string"), ("4g_cell_availability", "string", "4g_cell_availability", "float"), ("4g_packet_cssr", "string", "4g_packet_cssr", "float"), ("4g_volte_erab_success_rate", "string", "4g_volte_erab_success_rate", "float"), ("4g_volte_erab_drop_rate", "string", "4g_volte_erab_drop_rate", "float"), ("4g_drop_packet", "string", "4g_drop_packet", "float"), ("4g_volte_traffic", "string", "4g_volte_traffic", "float"), ("4g_packet_data_traffic_gb", "string", "4g_packet_data_traffic_gb", "float"), ("4g_user_throughput_dl_mbps", "string", "4g_user_throughput_dl_mbps", "float"), ("4g_utilization", "string", "4g_utilization", "float"), ("vendor", "string", "vendor", "string"), ("city", "string", "city", "string"), ("cluster", "string", "cluster", "string"), ("district", "string", "district", "string"), ("governorate", "string", "governorate", "string"), ("region", "string", "region", "string"), ("x_coordinate", "string", "x_coordinate", "string"), ("y_coordinate", "string", "y_coordinate", "string"), ("fdd_tdd_technology", "string", "fdd_tdd_technology", "string")], transformation_ctx="ChangeSchema_node1716744216335")

# # Write data back into Amazon S3
# AmazonS3_node1716476739276 = glueContext.getSink(path=f"s3://{bucket_name}/data-proc/", connection_type="s3", updateBehavior="UPDATE_IN_DATABASE", partitionKeys=["date"], enableUpdateCatalog=True, transformation_ctx="AmazonS3_node1716476739276")
# AmazonS3_node1716476739276.setCatalogInfo(catalogDatabase="data_set_db",catalogTableName="data_proc")
# AmazonS3_node1716476739276.setFormat("glueparquet", compression="snappy")
# AmazonS3_node1716476739276.writeFrame(ChangeSchema_node1716744216335)
# job.commit()