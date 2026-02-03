"""Sample plugin that registers an 'p-echo' command."""

def register(registry):
    def p_echo(args):
        print('[plugin] ' + ' '.join(args))
        return True

    registry.commands['p-echo'] = (p_echo, 'Plugin echo command')
