Story with preconditions:
  preconditions:
    files:
      example.story: |
        Create files:
          preconditions:
            thing:
              content: things
          scenario:
            - Create file
      engine.py: |
        from hitchstory import BaseEngine, StorySchema
        from strictyaml import Str, Map, MapPattern

        def output(contents):
            with open("output.txt", 'a') as handle:
                handle.write("{0}\n".format(contents))

        class Engine(BaseEngine):
            schema = StorySchema(
                preconditions=Map({"thing": MapPattern(Str(), Str()),}),
            )

            def create_file(self):
                assert type(self.preconditions['thing']['content']) is str
                assert type(list(self.preconditions.keys())[0]) is str
                output(self.preconditions['thing']['content'])
  scenario:
    - Run command: |
        from hitchstory import StoryCollection
        from pathquery import pathq
        from engine import Engine

        print(StoryCollection(pathq(".").ext("story"), Engine()).one().play().report())
    - Output is: things