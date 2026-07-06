###############################################################################
#                             requirements: start                             #
###############################################################################
# CKAN core supports this short syntax. But internally it's unfolds into
## remote-ckan = https://github.com/ckan/ckan tag ckan-2.10.4
# if you want to use CKAN fork or specific commit, use this full specification
ckan_tag = ckan-2.11.5

ext_list = \
	scheming \
	envvars \
	saml \
	xloader \
	ingest \
	downloadall \
	harvest theming

remote-scheming = https://github.com/ckan/ckanext-scheming.git tag release-3.1.0
remote-envvars = https://github.com/ckan/ckanext-envvars tag v0.0.6
remote-saml = https://github.com/DataShades/ckanext-saml.git tag v0.3.10
remote-ingest = https://github.com/DataShades/ckanext-ingest tag v1.4.6
remote-harvest = https://github.com/ckan/ckanext-harvest.git tag v1.6.1
remote-downloadall = https://github.com/SDM-TIB/ckanext-downloadall.git commit 4e0965e # 2026-04-09, +1 commit after v0.3.0
remote-theming = https://github.com/dataShades/ckanext-theming commit 3651549 # 2026-06-06

package_extras-remote-googleanalytics = requirements
package_extras-remote-files = opendal,libcloud
package_extras-remote-resource-indexer = pdf

###############################################################################
#                              requirements: end                              #
###############################################################################

# version of CDM pulled during `make-prepare`. Use version tag to prevent
# undesirable udates
_version = master

# import all rules defined in `deps.mk`. This file will be pulled by `make prepare`
-include deps.mk

prepare:  ## download CDM rules
	curl -O https://raw.githubusercontent.com/DataShades/ckan-deps-installer/$(_version)/deps.mk


test-config = test_config/test.ini

test-server:  ## start server for frontend testing
ifeq ($(dirty-server),)
	yes | ckan -c $(test-config) db clean
	ckan -c $(test-config) db upgrade
	yes | ckan -c$(test-config) sysadmin add admin password=password123 email=admin@test.net
endif
	ckan -c $(test-config) run -t


serve-docs: ## serve documentation via HTTP
	zensical serve
