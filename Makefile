###############################################################################
#                             requirements: start                             #
###############################################################################
# CKAN core supports this short syntax. But internally it's unfolds into
## remote-ckan = https://github.com/ckan/ckan tag ckan-2.10.4
# if you want to use CKAN fork or specific commit, use this full specification
# ckan_tag = ckan-2.12.0
remote-ckan = https://github.com/ckan/ckan commit 0e1d753 # dev-v2.12, 2026-08-03

ext_list = \
	scheming \
	envvars \
	saml \
	xloader \
	ingest \
	downloadall \
	harvest theming fpx

remote-scheming = https://github.com/ckan/ckanext-scheming.git commit ea79dc5 # 2026-07-06
remote-envvars = https://github.com/ckan/ckanext-envvars tag v0.0.6
remote-saml = https://github.com/DataShades/ckanext-saml.git tag v0.4.1
remote-ingest = https://github.com/DataShades/ckanext-ingest tag v1.4.6
remote-harvest = https://github.com/ckan/ckanext-harvest.git commit 1a9a987 # 2026-06-19
remote-downloadall = https://github.com/DataShades/ckanext-downloadall commit c2a3848 # 2026-07-15
remote-theming = https://github.com/dataShades/ckanext-theming commit 12c6ded # 2026-08-14
remote-fpx = https://github.com/DataShades/ckanext-fpx tag v0.7.1

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
