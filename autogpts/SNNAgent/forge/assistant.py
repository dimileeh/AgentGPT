from openai import OpenAI
import time
import concurrent.futures

client = OpenAI(default_headers={"OpenAI-Beta": "assistants=v2"})

class Thread:
    def __init__(self, user_id):
        self.user_id = user_id
        self.thread = None

    def create(self, messages=None):
        self.thread = client.beta.threads.create(messages=messages)
        print(f"Created a new thread with id: {self.thread.id}")

    def retrieve(self, thread_id):
        self.thread = client.beta.threads.retrieve(thread_id)

    def delete(self, thread_id):
        response = client.beta.threads.delete(thread_id)
        if response.deleted == True:
            self.thread = None

    def add_message(self, message):
        client.beta.threads.messages.create(
                thread_id=self.thread.id,
                role="user",
                content=message
                )

    def get_messages(self, limit=20, order='asc', after=None, before=None):
        thread_messages = client.beta.threads.messages.list(self.thread.id, limit=limit, order=order, after=after, before=before)
        # for msg in thread_messages:
        #     print(f"{msg.created_at} -- {msg.role}: {' '.join([c.text.value for c in msg.content if c.type == 'text'])}")
        # print("\n---\n")
        for msg in thread_messages:
            return ' '.join([c.text.value for c in msg.content if c.type == 'text'])
        # return [' '.join([c.text.value for c in msg.content if c.type == 'text']) for msg in thread_messages]
        # return thread_messages


class Assistant:
    def __init__(self):
        self.assistant = None

    def list_all(self):
        my_assistants = client.beta.assistants.list(
                order="desc",
                limit="20",
                )
        print(my_assistants.data)

    def retrieve(self, assistant_id):
        self.assistant = client.beta.assistants.retrieve(assistant_id)

    def create(self, name, instructions, model="gpt-4o", tools=None, files=None):
        self.assistant = client.beta.assistants.create(
                name=name,
                instructions=instructions,
                tools=tools,
                model=model
                )

    def delete(self, assistant_id):
        response = client.beta.assistants.delete(assistant_id)
        print(response)
        if self.assistant.id == assistant_id:
            self.assistant = None

    def run(self, thread_id, additional_instructions=None):
        _run = client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=self.assistant.id,
                additional_instructions=additional_instructions
                )

        counter = 0
        while _run.status not in ['completed', 'failed', 'cancelled', 'expired', 'requires_action']:
            _run = self.retrieve_run_with_timeout(thread_id, _run.id, retries=10)
            print(f"Run {_run.id} status: {_run.status} counter: {counter}")
            time.sleep(1)
            counter += 1
            if counter > 120:
                break

        if _run.status != 'completed':
            print(f"Run NOT completed! {_run}")
            raise Exception(f"Run NOT completed! {_run}")

        return _run

    def retrieve_run(self, thread_id, run_id):
        _run = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
                )
        return _run

    def retrieve_run_with_timeout(self, thread_id, run_id, retries=3, timeout=10):
        for attempt in range(retries):
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # Pass parameters to the function here
                future = executor.submit(self.retrieve_run, thread_id, run_id)
                try:
                    # Attempt to get the result within the specified timeout duration
                    result = future.result(timeout=timeout)
                    return result
                except concurrent.futures.TimeoutError:
                    print(f"Attempt {attempt + 1} timed out. Retrying...")
        return "Failed after retries"