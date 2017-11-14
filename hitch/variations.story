Variations:
  description: |
    Some stories are very similar except for a few changed items. You
    can create substories within the same story in order to enumerate
    all of the possible permutations.
  given:
    example.story: |
      Create files:
        given:
          content: dog
          hierarchical content:
            x: 1
            y:
              - 42
        steps:
          - Do thing with precondition
          - Do other thing: dog
          - Do yet another thing
          - Do a fourth thing:
              animals:
                pond animal: frog
        variations:
          cat:
            given:
              content: cat
    setup: |
      from hitchstory import StoryCollection, BaseEngine, StorySchema, validate
      from strictyaml import Map, Seq, Int, Str, Optional
      from pathquery import pathq
      from ensure import Ensure


      class Engine(BaseEngine):
          schema = StorySchema(
              given={
                  "content": Str(),
                  Optional("hierarchical content"): Map({
                      "x": Int(),
                      "y": Seq(Str()),
                  }),
              },
          )

          def do_other_thing(self, parameter):
              assert type(parameter) is str
              print(parameter)

          def do_thing_with_precondition(self):
              assert type(self.given['content']) is str
              print(self.given['content'])

          def do_yet_another_thing(self):
              assert type(self.given['hierarchical content']['y'][0]) is str
              print(self.given['hierarchical content']['y'][0])

          @validate(animals=Map({"pond animal": Str()}))
          def do_a_fourth_thing(self, animals=None):
              assert type(animals['pond animal']) is str
              print(animals['pond animal'])

      story_collection = StoryCollection(pathq(".").ext("story"), Engine())
  variations:
    Play:
      steps:
      - Run:
          code: |
            story_collection.shortcut("cat").play().report()
          will output: |-
            cat
            dog
            42
            frog

    Non-variations:
      steps:
      - Run:
          code: |
            Ensure([
                story.name for story in story_collection.non_variations().ordered_by_name()
            ]).equals(
                ["Create files", ]
            )

    Variations on story:
      steps:
      - Run:
          code: |
            Ensure([
                story.name for story in story_collection.named("Create files").variations
            ]).equals(
                ["Create files/cat"],
            )

    Only children:
      steps:
      - Run:
          code: |
            Ensure([
                story.name for story in story_collection.only_uninherited().ordered_by_name()
            ]).equals(
                ["Create files/cat"],
            )
