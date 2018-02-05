import os
import sys
import asyncio
import re
import pickle
import json
import datetime
from logs import init_loggers
import discord
from discord.ext import commands
import spelling
from errors import custom_error_handling
from random import *
from dateutil.relativedelta import relativedelta

tessdata_dir_config = "--tessdata-dir 'C:\\Program Files (x86)\\Tesseract-OCR\\tessdata' "
xtraconfig = "-l eng -c tessedit_char_blacklist=&|=+%#^*[]{};<> -psm 6"

if os.name == 'nt':
    tesseract_config = tessdata_dir_config + xtraconfig
else:
    tesseract_config = xtraconfig

logger = init_loggers()


def _get_prefix(bot, message):
    server = message.server
    try:
        set_prefix = bot.server_dict[server.id]["prefix"]
    except KeyError:
        set_prefix = None
    default_prefix = bot.config["default_prefix"]
    return set_prefix or default_prefix


RotomDex = commands.Bot(command_prefix=_get_prefix)
RotomDex.remove_command("help")
custom_error_handling(RotomDex, logger)

try:
    with open(os.path.join('data', 'serverdict'), "rb") as fd:
        RotomDex.server_dict = pickle.load(fd)
    logger.info("Serverdict Loaded Successfully")
except OSError:
    logger.info("Serverdict Not Found - Looking for Backup")
    try:
        with open(os.path.join('data', 'serverdict_backup'), "rb") as fd:
            RotomDex.server_dict = pickle.load(fd)
        logger.info("Serverdict Backup Loaded Successfully")
    except OSError:
        logger.info("Serverdict Backup Not Found - Creating New Serverdict")
        RotomDex.server_dict = {}
        with open(os.path.join('data', 'serverdict'), "wb") as fd:
            pickle.dump(RotomDex.server_dict, fd, -1)
        logger.info("Serverdict Created")

server_dict = RotomDex.server_dict




config = {}
pkmn_info = {}
type_chart = {}
type_list = []
raid_info = {}
active_raids = []
gym_info_list = {}
egg_timer = 0
raid_timer = 0
icon_list = {}
GOOGLE_API_KEY = ""
GOOGLE_MAPS_URL = "https://maps.googleapis.com/maps/api/staticmap?center={latlong}&markers=color:red%7C{latlong}&maptype=roadmap&size=250x125&zoom=15&key=" + GOOGLE_API_KEY
INVITE_CODE = "AUzEXRU"


# Append path of this script to the path of
# config files which we're loading.
# Assumes that config files will always live in the same directory.
script_path = os.path.dirname(os.path.realpath(__file__))


def load_config():
    global config
    global pkmn_info
    global type_chart
    global type_list
    global raid_info
    global egg_timer
    global raid_timer
    global icon_list
    global GOOGLE_API_KEY
    global GOOGLE_MAPS_URL

    # Load configuration
    with open("config.json", "r") as fd:
        config = json.load(fd)

    # Set up message catalog access
    # language = gettext.translation('clembot', localedir='locale', languages="en")
    # language.install()
    # pokemon_language = [config['pokemon-language']]
    # pokemon_path_source = os.path.join('locale', '{0}', 'pkmn.json').format(config['pokemon-language'])

    # Load Pokemon list and raid info
    with open(os.path.join('data', 'pkmn.json'), "r") as fd:
        pkmn_info = json.load(fd)

    with open(os.path.join('data', "icon.json"), "r") as fd:
        icon_list = json.load(fd)

    # Set spelling dictionary to our list of Pokemon
    spelling.set_dictionary(pkmn_info['pokemon_list'])

    # gymutil.load_gyms()


load_config()

RotomDex.config = config


event_loop = asyncio.get_event_loop()

def get_pokemon_image_url(pokedex_number):
    # url = icon_list.get(str(pokedex_number))
    url = "https://raw.githubusercontent.com/TrainingB/PokemonGoImages/master/images/pkmn/{0}_.png?cache=0".format(str(pokedex_number).zfill(3))
    if url:
        return url
    else:
        return "http://floatzel.net/pokemon/black-white/sprites/images/{pokedex}.png".format(pokedex=pokedex_number)

async def _print(owner, message):
    if 'launcher' in sys.argv[1:]:
        if 'debug' not in sys.argv[1:]:
            await RotomDex.send_message(owner, message)
    #print(message)
    logger.info(message)

def _(text):
    return text

# Given a string, if it fits the pattern :emoji name:,
# and <emoji_name> is in the server's emoji list, then
# return the string <:emoji name:emoji id>. Otherwise,
# just return the string unmodified.
def parse_emoji(server, emoji_string):
    if emoji_string[0] == ':' and emoji_string[-1] == ':':
        emoji = discord.utils.get(server.emojis, name=emoji_string.strip(':'))
        if emoji:
            emoji_string = "<:{0}:{1}>".format(emoji.name, emoji.id)
        else:
            emoji_string = "{0}".format(emoji_string.strip(':').capitalize())

    return emoji_string


# Given a list of weaknesses, return a
# space-separated string of their type IDs,
# as defined in the type_id_dict
def weakness_to_str(server, weak_list):
    ret = ""
    for weakness in weak_list:
        # Handle an "x2" postfix defining a double weakness
        x2 = ""
        if weakness[-2:] == "x2":
            weakness = weakness[:-2]
            x2 = "x2"

        # Append to string
        ret += parse_emoji(server, config['type_id_dict'][weakness]) + x2 + " "

    return ret


@RotomDex.command(pass_context=True, hidden=True)
async def about(ctx):
    """Shows info about RotomDex"""

    author_repo = "https://github.com/TrainingB"
    author_name = "TrainingB"
    bot_repo = author_repo + "/RotomDex"
    server_url = "https://discord.gg/{invite}".format(invite=INVITE_CODE)
    owner = RotomDex.owner
    channel = ctx.message.channel
    uptime_str = await _uptime(RotomDex)
    embed_colour = ctx.message.server.me.colour or discord.Colour.lighter_grey()

    about = ("I'm RotomDex! A Basic Contest bot for Discord!\n\n"
             "I was made by [{author_name}]({author_repo}).\n\n"
             "[Join our server]({server_invite}) if you have any questions or feedback.\n\n"
             "".format(author_name=author_name, author_repo=author_repo, server_invite=server_url))

    member_count = 0
    server_count = 0
    for server in RotomDex.servers:
        server_count += 1
        member_count += len(server.members)

    embed = discord.Embed(colour=embed_colour, icon_url=RotomDex.user.avatar_url)
    embed.add_field(name="About Clembot", value=about, inline=False)
    embed.add_field(name="Owner", value=owner)
    embed.add_field(name="Servers", value=server_count)
    embed.add_field(name="Members", value=member_count)
    embed.add_field(name="Uptime", value=uptime_str)
    embed.set_footer(text="For support, contact us on our Discord server. Invite Code: AUzEXRU")

    try:
        await RotomDex.send_message(channel, embed=embed)
    except discord.HTTPException:
        await RotomDex.send_message(channel, "I need the `Embed links` permission to send this")


async def _uptime(bot):
    """Shows info about Clembot"""
    time_start = bot.uptime
    time_now = datetime.datetime.now()
    ut = (relativedelta(time_now, time_start))
    ut.years, ut.months, ut.days, ut.hours, ut.minutes
    if ut.years >= 1:
        uptime = "{yr}y {mth}m {day}d {hr}:{min}".format(yr=ut.years, mth=ut.months, day=ut.days, hr=ut.hours, min=ut.minutes)
    elif ut.months >= 1:
        uptime = "{mth}m {day}d {hr}:{min}".format(mth=ut.months, day=ut.days, hr=ut.hours, min=ut.minutes)
    elif ut.days >= 1:
        uptime = "{day} days {hr} hrs {min} mins".format(day=ut.days, hr=ut.hours, min=ut.minutes)
    elif ut.hours >= 1:
        uptime = "{hr} hrs {min} mins {sec} secs".format(hr=ut.hours, min=ut.minutes, sec=ut.seconds)
    else:
        uptime = "{min} mins {sec} secs".format(min=ut.minutes, sec=ut.seconds)

    return uptime


@RotomDex.event
async def on_ready():
    RotomDex.owner = discord.utils.get(RotomDex.get_all_members(), id=config["master"])
    await _print(RotomDex.owner, "Starting up...")  # prints to the terminal or cmd prompt window upon successful connection to Discord
    RotomDex.uptime = datetime.datetime.now()
    owners = []
    msg_success = 0
    msg_fail = 0
    servers = len(RotomDex.servers)
    users = 0
    for server in RotomDex.servers:
        users += len(server.members)
        try:
            if server.id not in server_dict:
                server_dict[server.id] = {'want_channel_list': [], 'offset': 0, 'welcome': False, 'welcomechan': '', 'wantset': False, 'raidset': False, 'wildset': False, 'team': False, 'want': False, 'other': False, 'done': False, 'raidchannel_dict' : {}}
        except KeyError:
            server_dict[server.id] = {'want_channel_list': [], 'offset': 0, 'welcome': False, 'welcomechan': '', 'wantset': False, 'raidset': False, 'wildset': False, 'team': False, 'want': False, 'other': False, 'done': False, 'raidchannel_dict': {}}

        owners.append(server.owner)

    embed = discord.Embed(colour=discord.Colour.green(), description="Rotom! That's right!").set_author(name="Rotomdex Startup Notification", icon_url=RotomDex.user.avatar_url)
    embed.add_field(name="**Servers Connected**", value=_(" {servers}").format(servers=servers), inline=True)
    embed.add_field(name="**Members Found**", value=_(" {members}").format(members=users), inline=True)
    await RotomDex.send_message(RotomDex.owner, embed=embed)

@RotomDex.event
async def on_message(message):
    #print(server_dict)
    if message.server is not None:
        if 'contest_channel' in server_dict[message.server.id]:
            if message.channel.id in server_dict[message.server.id]['contest_channel'] and server_dict[message.server.id]['contest_channel'][message.channel.id].get('started',False) == True:
                await contestEntry(message)
                return

    messagelist = message.content.split(" ")
    message.content = messagelist.pop(0).lower() + " " + " ".join(messagelist)
    await RotomDex.process_commands(message)

#   await maint_start()

# Convert an arbitrary string into something which
# is acceptable as a Discord channel name.
def sanitize_channel_name(name):
    # Remove all characters other than alphanumerics,
    # dashes, underscores, and spaces
    ret = re.sub(r"[^a-zA-Z0-9 _\-]", "", name)
    # Replace spaces with dashes
    ret = ret.replace(" ", "-")
    return ret

# Given a Pokemon name, return a list of its
# weaknesses as defined in the type chart
def get_weaknesses(species):
    # Get the Pokemon's number
    number = pkmn_info['pokemon_list'].index(species)
    # Look up its type
    pk_type = type_list[number]

    # Calculate sum of its weaknesses
    # and resistances.
    # -2 == immune
    # -1 == NVE
    #  0 == neutral
    #  1 == SE
    #  2 == double SE
    type_eff = {}
    for type in pk_type:
        for atk_type in type_chart[type]:
            if atk_type not in type_eff:
                type_eff[atk_type] = 0
            type_eff[atk_type] += type_chart[type][atk_type]

    # Summarize into a list of weaknesses,
    # sorting double weaknesses to the front and marking them with 'x2'.
    ret = []
    for type, effectiveness in sorted(type_eff.items(), key=lambda x: x[1], reverse=True):
        if effectiveness == 1:
            ret.append(type.lower())
        elif effectiveness == 2:
            ret.append(type.lower() + "x2")

    return ret



def get_name(pkmn_number):
    pkmn_number = int(pkmn_number) - 1
    name = pkmn_info['pokemon_list'][pkmn_number].capitalize()
    return name


@RotomDex.command(pass_context=True)
async def hide(ctx):
    await _hideChannel(ctx.message.channel)


async def _hideChannel(channel):
    try:
        print("hide: {channel}".format(channel=channel.name))

        readable = discord.PermissionOverwrite()
        readable.read_messages=False

        await RotomDex.edit_channel_permissions(channel, channel.server.default_role, readable)
    except Exception as error:
        print(error)



@RotomDex.command(pass_context=True)
async def lock(ctx):
    await _lockChannel(ctx.message.channel)



def _readOnly():
    readable = discord.PermissionOverwrite()
    readable.read_messages = True

    return readable

async def _lockChannel(channel):
    try:
        writeable = discord.PermissionOverwrite()
        writeable.send_messages = True

        readable = discord.PermissionOverwrite()
        readable.read_messages=True
        readable.send_messages=False

        await RotomDex.edit_channel_permissions(channel, channel.server.me, writeable)
        await RotomDex.edit_channel_permissions(channel, channel.server.default_role, readable)
    except Exception as error:
        print(error)


@RotomDex.command(pass_context=True)
async def unlock(ctx):
    await _unlockChannel(ctx.message.channel)


async def _unlockChannel(channel):
    try:
        writeable = discord.PermissionOverwrite()
        writeable.send_messages = True
        writeable.read_messages = True
        await RotomDex.edit_channel_permissions(channel, channel.server.default_role, writeable)
    except Exception as error:
        print(error)


@RotomDex.command(pass_context=True)
@commands.has_permissions(manage_server=True)
async def contest(ctx):
    await _contest(ctx.message)
    return


def add_contest_to_server_dict(serverid):
    if 'contest_channel' in server_dict[serverid]:
        return

    server_contest = {'contest_channel': {}}
    server_dict[serverid].update(server_contest)
    return


def generate_pokemon(option=None):

    if option is None:
        pokedex = randint(1, 383)
    else:
        option = option.upper()
        if option == 'TEST':
            pokedex = randint(1, 100)
        elif  option == 'GEN1':
            pokedex = randint(1, 151)
        elif  option == 'GEN2':
            pokedex = randint(152, 251)
        elif  option == 'GEN3':
            pokedex = randint(252, 383)
        elif option == 'GEN12':
            pokedex = randint(1, 251)
        else:
            pokedex = randint(1, 383)


    return pokedex


async def _contest(message):
    try:
        raid_split = message.clean_content.lower().split()
        del raid_split[0]

        option = "ALL"
        if len(raid_split) > 1:
            option = raid_split[1].upper()
            if option not in ["ALL", "TEST", "GEN1", "GEN2", "GEN3", "GEN12"]:
                await RotomDex.send_message(message.channel, "Rotom! valid options are : ALL,TEST,GEN1,GEN2,GEN3,GEN12")
                return

        everyone_perms = discord.PermissionOverwrite(read_messages=True,send_messages=False, add_reactions=True)
        my_perms = discord.PermissionOverwrite(read_messages=True,send_messages=True, manage_channel=True, manage_permissions=True, manage_messages=True, embed_links=True, attach_files=True, add_reactions=True, mention_everyone=True)

        channel_name = sanitize_channel_name(raid_split[0])

        if channel_name == "here":
            contest_channel = message.channel
        else:
            contest_channel = await RotomDex.create_channel(message.server, channel_name)

        await RotomDex.edit_channel_permissions(contest_channel, target=message.server.default_role, overwrite=everyone_perms)
        await RotomDex.edit_channel_permissions(contest_channel, target=message.server.me, overwrite=my_perms)

        pokedex = generate_pokemon(option)
        pokemon = get_name(pokedex)

        await RotomDex.send_message(message.channel, content="Rotom! A contest is about to take place in {channel}!".format(channel=contest_channel.mention))

        raid_embed = discord.Embed(title="Rotom! A contest is about to take place in this channel!", colour=discord.Colour.gold() , description="The first member to correctly guess (and spell) the randomly selected pokemon name will win!")
        raid_embed.add_field(name="**Option:**", value="{option}".format(option=option))
        raid_embed.add_field(name="**Rules:**", value="{rules}".format(rules="One pokemon per attempt per line!"))
        raid_embed.set_footer(text="Reported by @{author}".format(author=message.author.name), icon_url=message.author.avatar_url)
        raid_embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/396098777729204226/396103528554168320/imageedit_15_4199265561.png")
        await RotomDex.send_message(contest_channel, embed=raid_embed)


        embed = discord.Embed(colour=discord.Colour.gold(), description="Rotom! A contest channel has been created!").set_author(name="Rotomdex Contest Notification [{0}]".format(message.server), icon_url=RotomDex.user.avatar_url)
        embed.add_field(name="**Server:**", value="{member}".format(member=message.server.name), inline=True)
        embed.add_field(name="**Channel:**", value=" {member}".format(member=contest_channel.name), inline=True)
        embed.add_field(name="**Reported By:**", value="{member}".format(member=message.author.name), inline=True)
        embed.add_field(name="**Option**", value=" {member}".format(member=option), inline=True)
        embed.add_field(name="**Pokemon**", value=" {member}".format(member=pokemon), inline=True)
        # embed.add_field(name="**Weaknesses:**", value=_("{weakness_list}").format(weakness_list=weakness_to_str(message.channel.server, get_weaknesses(pokedex))), inline=True)


        raid_img_url = get_pokemon_image_url(pokedex)  # This part embeds the sprite
        embed.set_thumbnail(url=raid_img_url)
        await RotomDex.send_message(RotomDex.owner, embed=embed)
        if message.author.id != RotomDex.owner.id :
            await RotomDex.send_message(message.author, embed=embed)


        await RotomDex.send_message(contest_channel, "Rotom! {reporter} can start the contest anytime using `!ready` command".format(reporter=message.author.mention))

        add_contest_to_server_dict(message.server.id)
        contest_channel_dict = {contest_channel.id : {'pokemon' : pokemon, 'started': False, 'reported_by' : message.author.id , 'option' : option }}

        server_dict[message.server.id]['contest_channel'].update(contest_channel_dict)

    except Exception as error:
        print(error)

    return

@RotomDex.command(pass_context=True)
async def renew(ctx):

    message = ctx.message
    if 'contest_channel' in server_dict[message.server.id]:
        if server_dict[message.server.id]['contest_channel'][message.channel.id].get('started', True) == False:
            if ctx.message.author.id == server_dict[message.server.id]['contest_channel'][message.channel.id].get('reported_by', 0):

                option = server_dict[message.server.id]['contest_channel'][message.channel.id].get('option', "ALL")

                pokedex = generate_pokemon(option)
                pokemon = get_name(pokedex)

                contest_channel_dict = {message.channel.id : {'pokemon' : pokemon, 'started': False, 'reported_by' : message.author.id , 'option' : option }}
                server_dict[message.server.id]['contest_channel'].update(contest_channel_dict)

                embed = discord.Embed(colour=discord.Colour.gold(), description="Rotom! A contest channel has been created!").set_author(name="Rotomdex Contest Notification - {0}".format(message.server), icon_url=RotomDex.user.avatar_url)
                embed.add_field(name="**Channel:**", value=" {member}".format(member=message.channel.name), inline=True)
                embed.add_field(name="**Option**", value=" {member}".format(member=option), inline=True)
                embed.add_field(name="**Pokemon**", value=" {member}".format(member=pokemon), inline=True)
                embed.add_field(name="**Server:**", value="{member}".format(member=message.server.name), inline=True)
                embed.add_field(name="**Reported By:**", value="{member}".format(member=message.author.name), inline=True)
                raid_img_url = get_pokemon_image_url(pokedex)  # This part embeds the sprite
                embed.set_thumbnail(url=raid_img_url)
                await RotomDex.delete_message(ctx.message)
                await RotomDex.send_message(RotomDex.owner, embed=embed)
                if message.author.id != RotomDex.owner.id :
                    await RotomDex.send_message(message.author, embed=embed)


@RotomDex.command(pass_context=True)
async def ready(ctx):
    print(server_dict)
    message = ctx.message
    if 'contest_channel' in server_dict[message.server.id]:
        if server_dict[message.server.id]['contest_channel'][message.channel.id].get('started', True) == False:
            if ctx.message.author.id == server_dict[message.server.id]['contest_channel'][message.channel.id].get('reported_by', 0):

                role = message.server.default_role
                args = ctx.message.clean_content.lower().split()
                del args[0]
                if len(args) > 0:
                    role_name = args[0]
                    role = discord.utils.get(ctx.message.server.roles, name=role_name)
                    if role is None:
                        role = message.server.default_role

                everyone_perms = discord.PermissionOverwrite(read_messages=True, send_messages=True, add_reactions=True)
                await RotomDex.edit_channel_permissions(message.channel, target=role, overwrite=everyone_perms)

                contest_channel_started_dict = {'started': True}
                server_dict[message.server.id]['contest_channel'][message.channel.id].update(contest_channel_started_dict)

                raid_embed = discord.Embed(title="Rotom! The channel is open for submissions now!", colour=discord.Colour.gold())
                raid_embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/396098777729204226/396101362460524545/imageedit_14_9502845615.png")
                await RotomDex.send_message(message.channel, embed=raid_embed)
            else:
                await RotomDex.send_message(message.channel, content="Rotom! Only contest organizer can do this!")
            return


async def contestEntry(message, pokemon=None):

    if pokemon == None:
        pokemon = server_dict[message.server.id]['contest_channel'][message.channel.id]['pokemon']

    if pokemon.lower() == message.content.lower():
        del server_dict[message.server.id]['contest_channel'][message.channel.id]
        await RotomDex.add_reaction(message, '✅')
        await RotomDex.add_reaction(message, '🎉')

        raid_embed = discord.Embed(title="**We have a winner!🎉🎉🎉**",description="", colour=discord.Colour.dark_gold())

        raid_embed.add_field(name="**Winner:**", value="{member}".format(member=message.author.mention), inline=True)
        raid_embed.add_field(name="**Winning Entry:**", value="{pokemon}".format(pokemon=pokemon), inline=True)
        raid_embed.set_thumbnail(url="https://cdn.discordapp.com/avatars/{user.id}/{user.avatar}.{format}".format(user=message.author, format="jpg"))
        # raid_embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/396098777729204226/396106669622296597/imageedit_17_5142594467.png")

        await RotomDex.send_message(message.channel, embed=raid_embed)

        await RotomDex.send_message(message.channel, content="Rotom! Congratulations {winner}!".format(winner=message.author.mention))

    elif message.content.lower() in pkmn_info['pokemon_list']:
        await RotomDex.add_reaction(message, '🔴')
    return


try:
    event_loop.run_until_complete(RotomDex.start(config['bot_token']))
except discord.LoginFailure:
    logger.critical("Invalid token")
    event_loop.run_until_complete(RotomDex.logout())
    RotomDex._shutdown_mode = 0
except KeyboardInterrupt:
    logger.info("Keyboard interrupt detected. Quitting...")
    event_loop.run_until_complete(RotomDex.logout())
    RotomDex._shutdown_mode = 0
except Exception as e:
    logger.critical("Fatal exception", exc_info=e)
    event_loop.run_until_complete(RotomDex.logout())
finally:
    pass

sys.exit(RotomDex._shutdown_mode)
