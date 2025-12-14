################################################################################
#
# aios-agent
#
################################################################################

AIOS_AGENT_VERSION = 1.0.0
AIOS_AGENT_SITE = $(BR2_EXTERNAL_AIOS_EXTERNAL_PATH)/../..
AIOS_AGENT_SITE_METHOD = local
AIOS_AGENT_DEPENDENCIES = python3 aios-core

define AIOS_AGENT_INSTALL_TARGET_CMDS
	# Install agent daemon
	$(INSTALL) -D -m 0755 $(@D)/core/daemon/aios-agent.py \
		$(TARGET_DIR)/usr/lib/aios/agent/aios-agent.py
	
	# Install systemd service
	$(INSTALL) -D -m 0644 $(@D)/core/systemd/aios-agent.service \
		$(TARGET_DIR)/usr/lib/systemd/system/aios-agent.service
	
	# Enable service
	mkdir -p $(TARGET_DIR)/etc/systemd/system/multi-user.target.wants
	ln -sf /usr/lib/systemd/system/aios-agent.service \
		$(TARGET_DIR)/etc/systemd/system/multi-user.target.wants/aios-agent.service
endef

$(eval $(generic-package))
