from forge.actions import ActionRegister
from forge.sdk import (
    Agent,
    AgentDB,
    ForgeLogger,
    Step,
    StepRequestBody,
    Task,
    TaskRequestBody,
    Workspace,
    PromptEngine,
)

import json
import pprint
import re
import os

from forge.llm import (
    chat_completion_request,
)

from forge.assistant import (
    Assistant,
    Thread,
)

LOG = ForgeLogger(__name__)


class ForgeAgent(Agent):
    """
    The goal of the Forge is to take care of the boilerplate code, so you can focus on
    agent design.

    There is a great paper surveying the agent landscape: https://arxiv.org/abs/2308.11432
    Which I would highly recommend reading as it will help you understand the possabilities.

    Here is a summary of the key components of an agent:

    Anatomy of an agent:
         - Profile
         - Memory
         - Planning
         - Action

    Profile:

    Agents typically perform a task by assuming specific roles. For example, a teacher,
    a coder, a planner etc. In using the profile in the llm prompt it has been shown to
    improve the quality of the output. https://arxiv.org/abs/2305.14688

    Additionally, based on the profile selected, the agent could be configured to use a
    different llm. The possibilities are endless and the profile can be selected
    dynamically based on the task at hand.

    Memory:

    Memory is critical for the agent to accumulate experiences, self-evolve, and behave
    in a more consistent, reasonable, and effective manner. There are many approaches to
    memory. However, some thoughts: there is long term and short term or working memory.
    You may want different approaches for each. There has also been work exploring the
    idea of memory reflection, which is the ability to assess its memories and re-evaluate
    them. For example, condensing short term memories into long term memories.

    Planning:

    When humans face a complex task, they first break it down into simple subtasks and then
    solve each subtask one by one. The planning module empowers LLM-based agents with the ability
    to think and plan for solving complex tasks, which makes the agent more comprehensive,
    powerful, and reliable. The two key methods to consider are: Planning with feedback and planning
    without feedback.

    Action:

    Actions translate the agent's decisions into specific outcomes. For example, if the agent
    decides to write a file, the action would be to write the file. There are many approaches you
    could implement actions.

    The Forge has a basic module for each of these areas. However, you are free to implement your own.
    This is just a starting point.
    """

    def __init__(self, database: AgentDB, workspace: Workspace):
        """
        The database is used to store tasks, steps and artifact metadata. The workspace is used to
        store artifacts. The workspace is a directory on the file system.

        Feel free to create subclasses of the database and workspace to implement your own storage
        """
        super().__init__(database, workspace)
        self.abilities = ActionRegister(self)

    async def create_task(self, task_request: TaskRequestBody) -> Task:
        """
        The agent protocol, which is the core of the Forge, works by creating a task and then
        executing steps for that task. This method is called when the agent is asked to create
        a task.

        We are hooking into function to add a custom log message. Though you can do anything you
        want here.
        """
        task = await super().create_task(task_request)
        LOG.info(
            f"📦 Task created: {task.task_id} input: {task.input[:40]}{'...' if len(task.input) > 40 else ''}"
        )
        return task

    async def get_task(self, task_id: str) -> Task:
        """
        Get a task by ID.
        """
        LOG.debug(f"Getting task with ID: {task_id}...")
        task = await self.db.get_task(task_id)
        return task

    async def call_llm(self, messages):
        try:
            # Define the parameters for the chat completion request
            chat_completion_kwargs = {
                "messages": messages,
                "model": "gpt-4o", #"gemini-1.5-pro-preview-0514", #"gemini-1.5-flash-preview-0514", # "gpt-4o", #"mixtral-8x7b-32768", #"gpt-4-0125-preview",
            }
            # Make the chat completion request and parse the response
            chat_response = await chat_completion_request(**chat_completion_kwargs)
            content = chat_response.choices[0].message.content
            # content = chat_response["choices"][0]["message"]["content"]
            answer = content

            # Log the answer for debugging purposes
            LOG.info("ANSWER FROM MODEL:" + pprint.pformat(answer))

            messages.append({'role': 'assistant', 'content': json.dumps(answer)})

            return answer

        except json.JSONDecodeError as e:
            # Handle JSON decoding errors
            LOG.error(f"Unable to decode chat response in call_llm: {chat_response}, \n\n{content}\n\n ERROR: {e}")
        except Exception as e:
            # Handle other exceptions
            LOG.error(f"Unable to generate chat response: {e}")

    def call_assistant(self, assistant: Assistant, thread: Thread, message: str, additional_instructions: str=None):
        thread.add_message(message)
        assistant.run(thread_id=thread.thread.id, additional_instructions=additional_instructions)
        try:
            answer = json.loads(thread.get_messages(limit=1, order='desc'), strict=False)
        except json.JSONDecodeError as e:
            # Handle JSON decoding errors
            LOG.error(f"Unable to decode chat response: {thread.get_messages(limit=1, order='desc')}")
            return None
        LOG.info("ANSWER FROM ASSISTANT:" + pprint.pformat(answer))
        return answer


    async def execute_step(self, task_id: str, step_request: StepRequestBody) -> Step:
        """
        For a tutorial on how to add your own logic please see the offical tutorial series:
        https://aiedge.medium.com/autogpt-forge-e3de53cc58ec

        The agent protocol, which is the core of the Forge, works by creating a task and then
        executing steps for that task. This method is called when the agent is asked to execute
        a step.

        The task that is created contains an input string, for the benchmarks this is the task
        the agent has been asked to solve and additional input, which is a dictionary and
        could contain anything.

        If you want to get the task use:

        ```
        task = await self.db.get_task(task_id)
        ```

        The step request body is essentially the same as the task request and contains an input
        string, for the benchmarks this is the task the agent has been asked to solve and
        additional input, which is a dictionary and could contain anything.

        You need to implement logic that will take in this step input and output the completed step
        as a step object. You can do everything in a single step or you can break it down into
        multiple steps. Returning a request to continue in the step output, the user can then decide
        if they want the agent to continue or not.
        """

        # Firstly we get the task this step is for so we can access the task input
        task = await self.get_task(task_id)

        if (step_request.input is None):
            # First, call list_steps to get the total number of steps
            _, pagination = await self.db.list_steps(task_id=task_id, page=1, per_page=1)
            total_steps = pagination.total_items

            # Calculate the last page number
            last_page = total_steps

            # Now, call list_steps with the last page number
            steps, _ = await self.db.list_steps(task_id=task_id, page=last_page, per_page=1)

            # The last step will be the last item in the returned list
            step = steps[-1] if steps else None
        else:
            # Create a new step in the database

            first_input = StepRequestBody(input=step_request.input, name=step_request.name or "First Step")
            step = await self.db.create_step(
                task_id=task_id, input=first_input, is_last=False
            )

        if (step.is_last):
            _, pagination = await self.db.list_artifacts(task_id=task_id, page=1, per_page=1)
            total_artifacts = pagination.total_items

            # Now, call list_artifacts with the last page number
            if (total_artifacts > 0):
                artifacts, _ = await self.db.list_artifacts(task_id=task_id, page=1, per_page=total_artifacts)

                for artifact in artifacts:
                    updated_artifact = await self.db.update_artifact(artifact_id=artifact.artifact_id, step_id=step.step_id)
                    print("ARTIFACTS: ", updated_artifact)

            step = await self.db.update_step(
                task_id=task_id,
                step_id=step.step_id,
                output="The task has been completed.",
                status="completed",
            )
            return step

        print(f"EXECUTING STEP NOW: {task.input} --- {step.input}")

        # Log the message
        LOG.info(f"\t✅ Final Step completed: {step.step_id} input: {step.input}")

        is_assistant = False

        if (is_assistant):

            assistant = Assistant()
            # GPT 4: asst_EyJaRFiR0qHLYH7zrClNPPrb
            # GPT 3.5: asst_NeTCyTvidN3NbhcK07QyxNPC
            assistant.retrieve('asst_EyJaRFiR0qHLYH7zrClNPPrb')
            thread = Thread(task_id)

        # Initialize the PromptEngine with the "gpt-3.5-turbo" model
        prompt_engine = PromptEngine("gpt-3.5-turbo")

        if (not is_assistant):
            # Load the system and task prompts
            system_prompt = prompt_engine.load_prompt("system-format")

            # Initialize the messages list with the system prompt
            messages = [
                {"role": "system", "content": system_prompt},
            ]

        # Define the task parameters
        task_kwargs = {
            "task": task.input,
            "abilities": self.abilities.list_abilities_for_prompt(),
            "previous_actions": json.loads(step.additional_input.get("previous_actions", '[]') if step.additional_input is not None else '[]'),
            "previous_output": json.loads(step.additional_input.get("previous_output", '[]') if step.additional_input is not None else '[]'),
        }

        ability_names = list(self.abilities.list_abilities().keys())
        print(f"DEBUG ABILITY NAMES: {ability_names}")

        # Load the task prompt with the defined task parameters
        task_prompt = prompt_engine.load_prompt("task-step", **task_kwargs)

        print(f"DEBUG PROMPT: {task_prompt}")

        # Append the task prompt to the messages list
        messages.append({"role": "user", "content": f"{task_prompt}\n\n Your current step for this task is: {step.input}"})

        # print(f"DEBUG MESSAGES: {messages}")

        if (is_assistant):
            thread.create(messages)
            assistant.run(thread_id=thread.thread.id)

        try:
            # Regular expression pattern to remove the beginning and end delimiters
            pattern = r'^```json(.*)```$'
            if (is_assistant):
                input_string = thread.get_messages(limit=1, order='desc')
            else:
                input_string = await self.call_llm(messages)


            #check if input_string is a string
            if isinstance(input_string, str):
                # Check if the input string starts with ```json and ends with ```
                if input_string.startswith('```json') and input_string.endswith('```'):
                    # Use re.sub to remove the delimiters
                    json_string = re.sub(pattern, r'\1', input_string, flags=re.DOTALL)
                else:
                    # If the string does not have the delimiters, use it as is
                    json_string = input_string

                # Parse the JSON string using json.loads
                answer = json.loads(json_string, strict=False)
            else:
                answer = input_string

        except json.JSONDecodeError as e:
            # Handle JSON decoding errors
            if (is_assistant):
                LOG.error(f"Unable to decode chat response in execute step: {e}, {thread.get_messages(limit=1, order='desc')}")
            else:
                LOG.error(f"Unable to decode chat response in execute step: {e}, {input_string}")
            return step

        if (is_assistant):
            LOG.info("ANSWER FROM ASSISTANT:" + pprint.pformat(answer))

        # Extract the ability from the answer
        ability = answer.get("ability") if answer else None

        # while ability and ability.get("name", 'none') not in ['', 'none', 'None']:

        is_last_step = False

        if ability.get("name") not in ability_names:
            # output = answer["thoughts"]["speak"] if answer and answer.get('thoughts') and answer['thoughts'].get('speak') else "ERROR OCCURED"
            output = f"You've used an invalid ability name. Make sure you specify only a valid ability name in your output. Remember, you only have access to the following abilities: {ability_names}"
        else:
            try:
                step = await self.db.update_step(
                    task_id=task_id,
                    step_id=step.step_id,
                    status="running",
                )
                output = await self.abilities.run_action(
                    task_id, ability["name"], **ability.get("args", {})
                )

                #check if any new file created in the work directory is registered as an artifact
                for root, directories, files in os.walk((self.workspace.base_path / task_id).resolve()):
                    for filename in files:
                        found_artifact = await self.db.get_artifact_by_file_name(task_id, filename)
                        if found_artifact is None:
                            await self.db.create_artifact(task_id, filename, filename)
                
                if isinstance(output, bytes):
                    output = output.decode('utf-8')

                if ability.get("name", 'none') in ['finish', '', 'none', 'None']:
                    args = ability.get('args', {})
                    reason = args.get('reason', 'No reason provided')
                    # step = await self.db.update_step(
                    #     task_id=task_id,
                    #     step_id=step.step_id,
                    #     output=reason,
                    # )
                    is_last_step = True

            except Exception as e:
                LOG.error(f"Unable to run action: {e}")
                output = e

        print(f"DEBUG OUTPUT: {output}")

        if (is_assistant):
            answer = self.call_assistant(assistant, thread, f"The output of the step is: `{output}`.", additional_instructions=f"Perform the next step if required. If an unexpected output occured, determine if you used the right ability and if so, try selecting the right ability for the task, or fix the previous step if an explicit error has occured. If the goal of the task is achieved, call the `finish` ability.")
        else:
            if (is_last_step):
                messages.append({'role': 'user', 'content': f"You have finished the task and achieved its goal."})
                agent_output = reason
            else:
                messages.append({'role': 'user', 'content': f"The output of the previous step is: `{output}`. Verify that this output matches with the goal of the task you are given. Perform the next step if required. If an unexpected output occured, determine if you used the right ability and if so, try selecting the right ability for the task, or fix the previous step if an explicit error has occured. If the goal of the task is achieved, call the `finish` ability."})
                agent_output = answer["thoughts"]["speak"] if answer and answer.get('thoughts') and answer['thoughts'].get('speak') else "ERROR OCCURED"

            # answer = await self.call_llm(messages)
            # Set the step output to the "speak" part of the answer
            # Update the step in the database
            previous_actions = json.loads(step.additional_input.get("previous_actions", '[]') if step.additional_input is not None else '[]')
            previous_actions.append({"ability": answer["ability"], "output": str(output)})
            previous_output = json.loads(step.additional_input.get("previous_output", '[]') if step.additional_input is not None else '[]')
            previous_output.append(agent_output)
            step = await self.db.update_step(
                task_id=task_id,
                step_id=step.step_id,
                output=agent_output,
                additional_output={"previous_actions": json.dumps(previous_actions), "previous_output": json.dumps(previous_output)},
                status="completed",
            )

            next_input = StepRequestBody(input=messages[-1]['content'], name="Last Step" if is_last_step else "Next Step")
            next_step = await self.db.create_step(
                task_id=task_id, input=next_input, is_last=is_last_step,
                additional_input={"previous_actions": json.dumps(previous_actions), "previous_output": json.dumps(previous_output)}
            )
            print(f"CREATING NEXT STEP: {next_step.input}")


            # ability = answer.get("ability") if answer else None
            # # Set the step output to the "speak" part of the answer
            # output = answer["thoughts"]["speak"] if answer and answer.get('thoughts') and answer['thoughts'].get('speak') else "ERROR OCCURED"
            # step = await self.db.update_step(
            #     task_id=task_id,
            #     step_id=step.step_id,
            #     output=output,
            # )

        


        # Update the step in the database
        # step = await self.db.update_step(
        #     task_id=task_id,
        #     step_id=step.step_id,
        #     status="completed",
        #     # output=output,
        #     # additional_output=additional_output,
        # )

        # Return the completed step
        return step