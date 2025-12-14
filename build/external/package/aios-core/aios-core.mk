################################################################################
#
# aios-core
#
################################################################################

AIOS_CORE_VERSION = 1.0.0
AIOS_CORE_SITE = $(BR2_EXTERNAL_AIOS_EXTERNAL_PATH)/../..
AIOS_CORE_SITE_METHOD = local
AIOS_CORE_DEPENDENCIES = python3

define AIOS_CORE_INSTALL_TARGET_CMDS
	# Install HAL
	$(INSTALL) -D -m 0755 $(@D)/core/hal/aios-hal.py \
		$(TARGET_DIR)/usr/lib/aios/hal/aios-hal.py
	
	# Install CLI
	$(INSTALL) -D -m 0755 $(@D)/core/cli/aios \
		$(TARGET_DIR)/usr/bin/aios
	
	# Install configuration
	$(INSTALL) -D -m 0644 $(@D)/rootfs/etc/aios/agent.conf \
		$(TARGET_DIR)/etc/aios/agent.conf
	$(INSTALL) -D -m 0644 $(@D)/rootfs/etc/aios/agent.env \
		$(TARGET_DIR)/etc/aios/agent.env
	
	# Create directories
	$(INSTALL) -d -m 0755 $(TARGET_DIR)/var/lib/aios
	$(INSTALL) -d -m 0755 $(TARGET_DIR)/var/log/aios
endef

$(eval $(generic-package))
