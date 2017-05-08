"""This .py is heavly based off of discord.py's command system
i used it badly because i can't into decorators but it works so w/e
pls no sue or bully
"""
import inspect
import datetime

class Command:
    def __init__(self, name, callback, **kwargs):
        self.name = name
        if not isinstance(name, str) and not isinstance(name, list):
            raise TypeError('Name of a command must be a string or list.')
        self.callback = callback
        self.enabled = kwargs.get('enabled', True)
        self.aliases = kwargs.get('aliases', [])
        self.cooldown = kwargs.get('cooldown', 0)  # Per use cooldown
        self.mod_only = kwargs.get('mod_only', False)
        self.patreon_only = kwargs.get('patreon_only', False)
        self.patreon_vip_only = kwargs.get('patreon_vip_only', False)
        self.patreon_aliases = kwargs.get('patreon_aliases', [])
        self.patreon_vip_aliases = kwargs.get('patreon_vip_aliases', [])
        try:
            self.description = inspect.cleandoc(callback.__doc__)
        except AttributeError:
            # No docs
            self.description = ""
        self.hidden = kwargs.get('hidden', False)
        self.only_allow = kwargs.get('only_allow', [])
        self.prefix = kwargs.get('prefix', '')
        self.parent = None

class CommandGroup:
    def __init__(self, **kwargs):
        self.commands = {}
        super().__init__(**kwargs)

    def add_command(self, command):
        if not isinstance(command, Command):
            raise TypeError('The command passed must be a subclass of Command')
        
        if isinstance(self, Command):
            command.parent = self
        if isinstance(command.name, str):
            command.name = [command.name]
        command_list = command.name + command.aliases + command.patreon_aliases + command.patreon_vip_aliases
        for cmd in command_list:
            if cmd == "unwrap":
                t = datetime.date.today()
                if not (t >= datetime.date(t.year, 12, 20) and t <= datetime.date(t.year, 12, 27)):
                    continue
            if command.prefix + cmd in self.commands:
                raise TypeError('Command {0.name} is already registered.'.format(command))
            self.commands[command.prefix + cmd] = command

    def get_command(self, name):
        return self.commands.get(name, None)

    def command(self, *args, **kwargs):
        def decorator(func):
            result = command(*args, **kwargs)(func)
            self.add_command(result)
            return result
        return decorator


def command(name=None, cls=None, **attrs):
    if cls is None:
        cls = Command

    def decorator(func):
        if isinstance(func, Command):
          raise TypeError('Callback is already a command.')

        fname = name or func.__name__.lower()
        return cls(name=fname, callback=func, **attrs)
    return decorator


