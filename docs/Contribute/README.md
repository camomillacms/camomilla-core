# How to contribute 🤝

Any contribution is welcome! Whether you want to report a bug, suggest an enhancement, or write code, we are happy to help you. Please read the following guidelines before contributing.

### ✉️ Reporting bugs 
You can report bugs by creating an issue on the [issue tracker](https://github.com/camomillacms/camomilla-core/issues).

Please include as much information as possible, including:
- The version of Camomilla you are using
- The version of Django you are using
- The version of Python you are using
- The operating system you are using
- The steps to reproduce the bug
- The expected result
- The actual result
- Any other information that might be useful

### ☝️ Suggesting enhancements
You can suggest enhancements by creating an issue on the [issue tracker](https://github.com/camomillacms/camomilla-core/issues).

Enhancements can be anything from a new feature to a small improvement in the documentation.
Even if you are not sure about your idea, feel free to open an issue and discuss it with us. Every idea is welcome!

### 🧑‍💻 Your first code contribution
If you want to contribute to Camomilla by writing code, you can start by looking at the [issue tracker](https://github.com/camomillacms/camomilla-core/issues). There you can find issues that are marked as "good first issue" and are suitable for new contributors. If you want to work on an issue, please leave a comment on it so that we can assign it to you. If you want to work on something else, please open an issue first so that we can discuss it. This way we can avoid duplicated work and make sure that your contribution will be accepted. Once you have finished your work, you can open a pull request. We will review it and, if everything is fine, we will merge it. If you are not sure about something, feel free to open a pull request as soon as possible so that we can discuss it. We are always happy to help!

### 💅 Coding conventions
We try to follow the [Django coding style](https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/coding-style/). Please make sure to follow it when writing code for Camomilla. If you are not sure about something, feel free to ask us.
We also use `black` to format our code, so please make sure to run it before opening a pull request. You can run it by executing the following command:

```bash
$ make format
```


### 🉑 Commit Conventions
We use [semantic commit messages](https://www.conventionalcommits.org/en/v1.0.0/) to make it easier to understand the changes made in each commit. Please use the following format for your commit messages:
```
<type>(<scope>): <subject>
<body>
<footer>
```
Where:
- `<type>` is one of the following: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`
- `<scope>` is optional and can be used to specify the scope of the change (e.g. `camomilla`, `theme`, `admin`, etc.)
- `<subject>` is a short description of the change (max 72 characters)
- `<body>` is an optional longer description of the change
- `<footer>` is an optional footer that can be used to reference issues or pull requests (e.g. `Closes #123`, `Fixes #456`)

### 🧪 Running tests

We always test pull requests before merging them. To avoid issues, please make sure that your code passes the tests before opening a pull request. You can run the tests by executing the following command:

```bash
$ make test
```

We test against a variety of Django and Python versions, so please make sure that your code passes the tests for all of them. You can check the list of tested version in our [CI configuration](.github/workflows/ci.yml).