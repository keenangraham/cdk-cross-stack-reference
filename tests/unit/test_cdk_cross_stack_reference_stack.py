import aws_cdk as core
import aws_cdk.assertions as assertions

from cdk_cross_stack_reference.cdk_cross_stack_reference_stack import CdkCrossStackReferenceStack

# example tests. To run these tests, uncomment this file along with the example
# resource in cdk_cross_stack_reference/cdk_cross_stack_reference_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = CdkCrossStackReferenceStack(app, "cdk-cross-stack-reference")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
