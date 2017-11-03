from commandlib import run, Command, CommandError
import hitchpython
from hitchstory import StoryCollection, StorySchema, BaseEngine, exceptions, validate
from hitchrun import expected
from strictyaml import Str, Seq, Map, Optional
from pathquery import pathq
import hitchtest
import hitchdoc
from simex import DefaultSimex
from commandlib import python
from hitchrun import hitch_maintenance
from hitchrun import DIR
from hitchrunpy import ExamplePythonCode, HitchRunPyException
from hitchstory import expected_exception
from templex import Templex, NonMatching
import colorama
import re


class Engine(BaseEngine):
    """Python engine for running tests."""

    schema = StorySchema(
        given={
            Optional("base.story"): Str(),
            Optional("example.story"): Str(),
            Optional("example1.story"): Str(),
            Optional("example2.story"): Str(),
            Optional("example3.story"): Str(),
            Optional("engine.py"): Str(),
            Optional("setup"): Str(),
            Optional("code"): Str(),
        },
        about={
            Optional("tags"): Seq(Str()),
        },
    )

    def __init__(self, paths, settings):
        self.path = paths
        self.settings = settings

    def set_up(self):
        """Set up your applications and the test environment."""
        self.path.state = self.path.gen.joinpath("state")

        self.doc = hitchdoc.Recorder(
            hitchdoc.HitchStory(self),
            self.path.gen.joinpath('storydb.sqlite'),
        )

        if self.path.state.exists():
            self.path.state.rmtree(ignore_errors=True)
        self.path.state.mkdir()
        self.path.key.joinpath("code_that_does_things.py").copy(self.path.state)

        for filename in [
            "base.story", "example.story", "example1.story",
            "example2.story", "example3.story", "engine.py",
        ]:
            if filename in self.given:
                self.path.state.joinpath(filename).write_text(self.given[filename])

        self.python_package = hitchpython.PythonPackage(
            self.given.get('python_version', '3.5.0')
        )
        self.python_package.build()

        self.pip = self.python_package.cmd.pip
        self.python = self.python_package.cmd.python

        # Install debugging packages
        with hitchtest.monitor([self.path.key.joinpath("debugrequirements.txt")]) as changed:
            if changed:
                run(self.pip("install", "-r", "debugrequirements.txt").in_dir(self.path.key))

        # Uninstall and reinstall
        with hitchtest.monitor(
            pathq(self.path.project.joinpath("hitchstory")).ext("py")
        ) as changed:
            if changed:
                self.pip("uninstall", "hitchstory", "-y").ignore_errors().run()
                self.pip("install", ".").in_dir(self.path.project).run()

    @expected_exception(NonMatching)
    @expected_exception(HitchRunPyException)
    @validate(
        code=Str(),
        will_output=Str(),
        raises=Map({
            Optional("type"): Str(),
            Optional("message"): Str(),
        })
    )
    def run(self, code, will_output=None, raises=None):
        self.example_py_code = ExamplePythonCode(self.python, self.path.state)\
            .with_terminal_size(160, 24)\
            .with_setup_code(self.given.get('setup', ''))
        to_run = self.example_py_code.with_code(code)

        if self.settings.get("cprofile"):
            to_run = to_run.with_cprofile(
                self.path.profile.joinpath("{0}.dat".format(self.story.slug))
            )

        result = to_run.expect_exceptions().run() if raises is not None else to_run.run()

        result_output = result.output\
                              .replace(self.path.state, "/path/to")\
                              .replace(colorama.Fore.RED, "[[ RED ]]")\
                              .replace(colorama.Style.BRIGHT, "[[ BRIGHT ]]")\
                              .replace(colorama.Style.DIM, "[[ DIM ]]")\
                              .replace(colorama.Fore.RESET, "[[ RESET FORE ]]")\
                              .replace(colorama.Style.RESET_ALL, "[[ RESET ALL ]]")\

        result_output = re.sub(r"0x[0-9a-f]+", "0xfffffffffff", result_output)

        if will_output is not None:
            actual_output = '\n'.join([line.rstrip() for line in result_output.split("\n")])
            try:
                Templex(will_output).assert_match(actual_output)
            except NonMatching:
                if self.settings.get("overwrite artefacts"):
                    self.current_step.update(**{"will output": actual_output})
                else:
                    raise

        if raises is not None:
            exception_type = raises.get('type')
            message = raises.get('message')

            try:
                result = self.example_py_code.expect_exceptions().run()
                result.exception_was_raised(exception_type)
                exception_message = '\n'.join([
                    line.rstrip() for line in
                    result.exception
                          .message
                          .replace(colorama.Fore.RED, "[[ RED ]]")
                          .replace(colorama.Style.BRIGHT, "[[ BRIGHT ]]")
                          .replace(colorama.Style.DIM, "[[ DIM ]]")
                          .replace(colorama.Fore.RESET, "[[ RESET FORE ]]")
                          .replace(colorama.Style.RESET_ALL, "[[ RESET ALL ]]")
                          .replace(self.path.state, "/path/to")
                          .rstrip().split("\n")
                ])

                exception_message = re.sub(r"0x[0-9a-f]+", "0xfffffffffff", exception_message)
                Templex(exception_message).assert_match(message)
            except NonMatching:
                if self.settings.get("overwrite artefacts"):
                    new_raises = raises.copy()
                    new_raises['message'] = exception_message
                    self.current_step.update(raises=new_raises)
                else:
                    raise

    def long_form_exception_raised(self, artefact=None):
        try:
            self.result = ExamplePythonCode(
                self.given['code']
            ).with_setup_code(self.given.get('setup', ''))\
             .expect_exceptions()\
             .run(self.path.state, self.python)
            processed_message = self.result.exception.message.replace(self.path.state, "/path/to")
            assert processed_message == self.path.key.joinpath(
                "artefacts", "{0}.txt".format(artefact.replace(" ", "-").lower())
            ).bytes().decode('utf8')
        except AssertionError:
            if self.settings.get("overwrite artefacts"):
                self.path.key.joinpath(
                    "artefacts", "{0}.txt".format(artefact.replace(" ", "-").lower())
                ).write_text(processed_message)

    def raises_exception(self, message=None, exception_type=None):
        try:
            self.result = ExamplePythonCode(
                self.given['code']
            ).with_setup_code(self.given.get('setup', ''))\
             .expect_exceptions()\
             .run(self.path.state, self.python)

            import re
            self.result.exception_was_raised(exception_type=exception_type)
            processed_message = self.result.exception.message.replace(self.path.state, "/path/to")
            processed_message = re.compile(r'0x[0-9a-f]+').sub("0xffffffff", processed_message)
            assert message == processed_message
        except AssertionError:
            if self.settings.get("overwrite artefacts"):
                self.current_step.update(message=processed_message)

    def file_contents_will_be(self, filename, contents):
        file_contents = '\n'.join([
            line.rstrip() for line in
            self.path.state.joinpath(filename).bytes().decode('utf8').strip().split('\n')
        ])
        try:
            Templex(file_contents).assert_match(contents.strip())
        except NonMatching:
            if self.settings.get("overwrite artefacts"):
                self.current_step.update(contents=file_contents)
            else:
                raise

    def pause(self, message="Pause"):
        if hasattr(self, 'services'):
            self.services.start_interactive_mode()
        import IPython
        IPython.embed()
        if hasattr(self, 'services'):
            self.services.stop_interactive_mode()

    @expected_exception(FileNotFoundError)
    def output_is(self, expected_contents):
        output_contents = self.path.state.joinpath("output.txt").bytes().decode('utf8').strip()
        regex = DefaultSimex(
            open_delimeter="(((",
            close_delimeter=")))",
            exact=True,
        ).compile(expected_contents.strip())
        if regex.match(output_contents) is None:
            raise RuntimeError("Expected output:\n{0}\n\nActual output:\n{1}".format(
                expected_contents,
                output_contents,
            ))
        self.path.state.joinpath("output.txt").remove()

    def output_contains(self, expected_contents):
        output_contents = self.path.state.joinpath("output.txt").bytes().decode('utf8').strip()
        regex = DefaultSimex(
            open_delimeter="(((",
            close_delimeter=")))",
        ).compile(expected_contents.strip())
        if regex.search(output_contents) is None:
            raise RuntimeError("Expected to find:\n{0}\n\nActual output:\n{1}".format(
                expected_contents,
                output_contents,
            ))
        self.path.state.joinpath("output.txt").remove()

    @validate(changeable=Seq(Str()))
    def output_will_be(self, reference, changeable=None):
        output_contents = self.path.state.joinpath("output.txt")\
                                         .bytes()\
                                         .decode('utf8')\
                                         .strip()\
                                         .replace(self.path.state, "/path/to")

        artefact = self.path.key.joinpath(
            "artefacts", "{0}.txt".format(reference.replace(" ", "-").lower())
        )

        simex = DefaultSimex(
            open_delimeter="(((",
            close_delimeter=")))",
        )

        simex_contents = output_contents

        if changeable is not None:
            for replacement in changeable:
                simex_contents = simex.compile(replacement).sub(replacement, simex_contents)

        if not artefact.exists():
            artefact.write_text(simex_contents)
        else:
            if self.settings.get('overwrite artefacts'):
                artefact.write_text(simex_contents)
            else:
                if simex.compile(artefact.bytes().decode('utf8')).match(output_contents) is None:
                    raise RuntimeError("Expected to find:\n{0}\n\nActual output:\n{1}".format(
                        artefact.bytes().decode('utf8'),
                        output_contents,
                    ))

    def splines_reticulated(self):
        assert self.path.state.joinpath("splines_reticulated.txt").exists()
        self.path.state.joinpath("splines_reticulated.txt").remove()

    def llamas_ass_kicked(self):
        assert self.path.state.joinpath("kicked_llamas_ass.txt").exists()
        self.path.state.joinpath("kicked_llamas_ass.txt").remove()

    def file_was_created_with(self, filename="", contents=""):
        if not self.path.state.joinpath(filename).exists():
            raise RuntimeError("{0} does not exist".format(filename))
        if self.path.state.joinpath(filename).bytes().decode('utf8') != contents:
            raise RuntimeError("{0} did not contain {0}".format(filename, contents))

    def on_success(self):
        self.new_story.save()


@expected(exceptions.HitchStoryException)
def tdd(*words):
    """
    Run test with words.
    """
    print(
        StoryCollection(
            pathq(DIR.key).ext("story"),
            Engine(
                DIR,
                {
                    "overwrite artefacts": True,
                    "print output": True,
                },
            )
        ).shortcut(*words).play().report()
    )


@expected(exceptions.HitchStoryException)
def testfile(filename):
    """
    Run all stories in filename 'filename'.
    """
    print(
        StoryCollection(
            pathq(DIR.key).ext("story"), Engine(DIR, {"overwrite artefacts": False})
        ).in_filename(filename).ordered_by_name().play().report()
    )


@expected(exceptions.HitchStoryException)
def regression():
    """
    Continuos integration - run all tests and linter.
    """
    lint()
    print(
        StoryCollection(
            pathq(DIR.key).ext("story"), Engine(DIR, {})
        ).ordered_by_name().play().report()
    )


@expected(CommandError)
def lint():
    """
    Lint all code.
    """
    python("-m", "flake8")(
        DIR.project.joinpath("hitchstory"),
        "--max-line-length=100",
        "--exclude=__init__.py",
    ).run()
    python("-m", "flake8")(
        DIR.key.joinpath("key.py"),
        "--max-line-length=100",
        "--exclude=__init__.py",
    ).run()
    print("Lint success!")


def hitch(*args):
    """
    Use 'h hitch --help' to get help on these commands.
    """
    hitch_maintenance(*args)


def deploy(version):
    """
    Deploy to pypi as specified version.
    """
    NAME = "hitchstory"
    git = Command("git").in_dir(DIR.project)
    version_file = DIR.project.joinpath("VERSION")
    old_version = version_file.bytes().decode('utf8')
    if version_file.bytes().decode("utf8") != version:
        DIR.project.joinpath("VERSION").write_text(version)
        git("add", "VERSION").run()
        git("commit", "-m", "RELEASE: Version {0} -> {1}".format(
            old_version,
            version
        )).run()
        git("push").run()
        git("tag", "-a", version, "-m", "Version {0}".format(version)).run()
        git("push", "origin", version).run()
    else:
        git("push").run()

    # Set __version__ variable in __init__.py, build sdist and put it back
    initpy = DIR.project.joinpath(NAME, "__init__.py")
    original_initpy_contents = initpy.bytes().decode('utf8')
    initpy.write_text(
        original_initpy_contents.replace("DEVELOPMENT_VERSION", version)
    )
    python("setup.py", "sdist").in_dir(DIR.project).run()
    initpy.write_text(original_initpy_contents)

    # Upload to pypi
    python(
        "-m", "twine", "upload", "dist/{0}-{1}.tar.gz".format(NAME, version)
    ).in_dir(DIR.project).run()


def docgen():
    """
    Generate documentation.
    """
    docpath = DIR.project.joinpath("docs")

    if not docpath.exists():
        docpath.mkdir()

    documentation = hitchdoc.Documentation(
        DIR.gen.joinpath('storydb.sqlite'),
        'doctemplates.yml'
    )

    for story in documentation.stories:
        story.write(
            "rst",
            docpath.joinpath("{0}.rst".format(story.slug))
        )


def rerun(version="3.5.0"):
    """
    Rerun last example code block with specified version of python.
    """
    Command(DIR.gen.joinpath("py{0}".format(version), "bin", "python"))(
        DIR.gen.joinpath("state", "examplepythoncode.py")
    ).in_dir(DIR.gen.joinpath("state")).run()
