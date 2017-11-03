Descriptive parameters attached to story:
  given:
    example.story: |
      Build city:
        description: A great city. The best.
        jiras: JIRA-123, JIRA-124
        features: files, creating
        steps:
          - Reticulate splines

      Live in city:
        jiras: JIRA-789
        features: other
        steps:
          - Kick llama's ass
    setup: |
      from hitchstory import StoryCollection, BaseEngine, StorySchema
      from strictyaml import Map, Str, CommaSeparated, Optional
      from pathquery import pathq
      from code_that_does_things import reticulate_splines, kick_llamas_ass

      class Engine(BaseEngine):
          schema = StorySchema(
              about={
                  Optional("description"): Str(),
                  "jiras": CommaSeparated(Str()),
                  "features": CommaSeparated(Str()),
              },
          )

          def reticulate_splines(self):
              reticulate_splines()

          def kick_llamas_ass(self):
              kick_llamas_ass()

      story_collection = StoryCollection(pathq(".").ext("story"), Engine())
  variations:
    Run all stories:
      steps:
      - Run:
          code: story_collection.ordered_by_name().play()
      - Splines reticulated
      - Llama's ass kicked

    Run only filtered stories:
      steps:
      - Run:
          code: |
            story_collection.filter(lambda story: "JIRA-124" in story.about['jiras']).ordered_by_name().play()
      - Splines reticulated

