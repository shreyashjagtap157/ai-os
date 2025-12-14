################################################################################
#
# aios-ui
#
################################################################################

AIOS_UI_VERSION = 1.0.0
AIOS_UI_SITE = $(BR2_EXTERNAL_AIOS_EXTERNAL_PATH)/../..
AIOS_UI_SITE_METHOD = local
AIOS_UI_DEPENDENCIES = python3 aios-agent weston

define AIOS_UI_INSTALL_TARGET_CMDS
	# Install UI
	$(INSTALL) -D -m 0755 $(@D)/core/ui/aios-ui.py \
		$(TARGET_DIR)/usr/lib/aios/ui/aios-ui
	
	# Install systemd service
	$(INSTALL) -D -m 0644 $(@D)/core/systemd/aios-ui.service \
		$(TARGET_DIR)/usr/lib/systemd/system/aios-ui.service
	
	# Set as display manager
	mkdir -p $(TARGET_DIR)/etc/systemd/system/graphical.target.wants
	ln -sf /usr/lib/systemd/system/aios-ui.service \
		$(TARGET_DIR)/etc/systemd/system/graphical.target.wants/aios-ui.service
	
	# Set graphical target as default
	ln -sf /usr/lib/systemd/system/graphical.target \
		$(TARGET_DIR)/etc/systemd/system/default.target
endef

$(eval $(generic-package))
