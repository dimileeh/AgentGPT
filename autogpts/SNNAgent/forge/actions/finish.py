from forge.sdk.forge_log import ForgeLogger

from .registry import action

logger = ForgeLogger(__name__)


@action(
    name="finish",
    description="Use this to shut down once you have accomplished all of your goals,"
    " or when there are insurmountable problems that make it impossible"
    " for you to finish your task. Make sure to specify the 'reason' parameter to explain why you are invoking this action. "
    "Do not call this ability if you have not achieved your final goal of a given task!",
    parameters=[
        {
            "name": "reason",
            "description": "A summary to the user of how the goals were accomplished",
            "type": "string",
            "required": False,
        }
    ],
    output_type="None",
)
async def finish(
    agent,
    task_id: str,
    reason: str = "No Reason Provided",
) -> str:
    """
    A function that takes in a string and exits the program

    Parameters:
        reason (str): A summary to the user of how the goals were accomplished.
    Returns:
        A result string from create chat completion. A list of suggestions to
            improve the code.
    """
    logger.info(reason, extra={"title": "Shutting down...\n"})
    return reason
