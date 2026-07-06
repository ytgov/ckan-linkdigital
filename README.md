# ckanext-yukon

This extension is a CKAN extension that provides a new design for the Yukon
project.

## Deployment

To deploy this extension, you need to have a CKAN instance running. You can
follow the [official
documentation](https://docs.ckan.org/en/latest/maintaining/installing/index.html)
to install CKAN.

Additional information can be found in the [Deployment documentation](DEPLOYMENT.md).

## Installation


1. Install the project using [CKAN dependency manager](https://github.com/dataShades/ckan-deps-installer):

    ```sh
    make prepare
    make install
    ```

2. Link all files from `config/` folder to the directory with CKAN configuration
   ```sh
   ln -s $PWD/config/* /etc/ckan/default/
   ```

3. Create `default.ini` which will be included into `project.ini` file linked in the previous step:
   ```sh
   ckan generate config /etc/ckan/default/default.ini
   ```

3. Create `ckan.ini`
   ```sh
   ckan generate config /etc/ckan/default/ckan.ini
   ```

4. Copy and adapt all environment specific options (block `Environment
    settings`) from the `project.ini` into `ckan.ini`. Additionally, make sure `ckan.ini` extends `project.ini`:

    ```ini
    [app:main]
    use = config:project.ini
    # ...
    ```

5. Apply DB migrations:
   ```sh
   ckan db upgrade
   ```

## Config settings

...

## Developer installation

To install ckanext-yukon for development perform all steps from the normal
installation and additionally run `pip install -e '.[dev]'` from the extension
root.

## Tests

To run unit-tests, do:

```sh
pytest
```

The codebase also contains e2e tests, that are excluded from the test
collection by default. To run them, first start the test application in a
separate terminal session:

```sh
make test-server
```

and then run tests:

```sh
pytest -m playwright
```

## Project documentation

Install project for development and run the following command to start
documentation app on `http://localhost:8000`:

```sh
make serve-docs
```

## License

[AGPL](https://www.gnu.org/licenses/agpl-3.0.en.html)
