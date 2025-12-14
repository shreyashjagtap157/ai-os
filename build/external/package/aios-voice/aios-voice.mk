################################################################################
#
# aios-voice
#
################################################################################

AIOS_VOICE_VERSION = 1.0.0
AIOS_VOICE_SITE = $(BR2_EXTERNAL_AIOS_EXTERNAL_PATH)/../..
AIOS_VOICE_SITE_METHOD = local
AIOS_VOICE_DEPENDENCIES = python3 aios-agent portaudio espeak

define AIOS_VOICE_INSTALL_TARGET_CMDS
	# Install voice service
	$(INSTALL) -D -m 0755 $(@D)/core/voice/aios-voice.py \
		$(TARGET_DIR)/usr/lib/aios/voice/aios-voice.py
	
	# Install systemd service
	$(INSTALL) -D -m 0644 $(@D)/core/systemd/aios-voice.service \
		$(TARGET_DIR)/usr/lib/systemd/system/aios-voice.service
	
	# Enable service
	mkdir -p $(TARGET_DIR)/etc/systemd/system/multi-user.target.wants
	ln -sf /usr/lib/systemd/system/aios-voice.service \
		$(TARGET_DIR)/etc/systemd/system/multi-user.target.wants/aios-voice.service
endef

$(eval $(generic-package))
