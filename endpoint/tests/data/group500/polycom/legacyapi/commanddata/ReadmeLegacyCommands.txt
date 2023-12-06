# In order to facilitate migration, this header was removed from the
# legacycommands.txt file, and moved to this separate location. (It may
# continue to live separated from its original file.. that remains to be seen).
#
# Each command takes one line. Lines that start with the character '#' are
# comments. Comments are for adding notes and description and will be ignored
# by the command parser.
#
# Each command has many components separated by ',' (comma) character. Format
# of each command is below <command>,<type>,<internal use only>,
#    <should Translate Params>,<should Translate Results>,
#    <minimum params>[/<max params>],<response string>,<action string>
#
# where
#   <command> is the command that an api client sends to the api engine;
#   <type>    is the type of the command. This can be one of a small set of
#             built-in command handlers, or its a so-called custom
#             command handler. (The distinction is not too important at the
#             moment, since all strings in this field need to be declared and
#             registered)
#   <internal use only>	      if True, this command will be treated as
#                             undefined by top level calls to
#                             CommandProcessor.processCommand().
#
#   <should Translate Params> if True, any parameter passed on this command is
#                             translated using param translation table. Else
#                             (i.e False), the param is passed directly to the
#                             api command handler
#
#   <should Translate Results> if True, the result of the command handler will
#                              be translated using result translation table.
#
#   <minimum params>[/<max params>] <minimum params> is the minimum number of parameters that this command
#                     requires and <max params> is max params that are allowed.
#   <response string> is the response for the command
#   <action string>   depends on the type and the command itself.
#
# NOTES:
#  01) As a convenience, a comma can be used in the action string as is. If
#      you need to use a reserved character the following interal API status
#	   variables can be used:
#			%[chcomma]	expands to ','
#			%[chdollar]	expands to '$'
#			%[chpipe]	expands	to '|'
#
#  02) Special expansions (for result or action field)
#          Symbol  Expands to
#          ------  ------------------------------------------------------------
#			 $^	   root command (command prior to args up to first space)
#            $*    all the arguments (everything after the root command)
#			 $@	   full command (command including any explicit match cmd args)
#			 $#	   the string representaion of the number of user supplied args
#
#  03) All commands that start with the reserved character '_' are intended to
#      be internal. On one level this means that the help subsystem will filter
#      these commands from end user help.
#
#  04) Framework internal commands (which should also start with a '_' to keep
#      them out of user help, will have their <internal use only> (field #3)
#      set to True. This will inhibit them from being processed at the
#      CommandProcessor.processCommand() level if they are do not have a
#      superCommand (ie. are top level commands).
#
#  05) Fields not used are by convention with with the string "nop" (short for
#      no operation). <In the current incarnation of the framework, all fields
#      must contain something>
#
#  06) Since internal commands are now being prefaced with an underscore,
#      please maintain this file in alphabetic order in all cases.
#
#  07) The comment character '#' is not honored mid line and is equivalent to
#      the C/C++ '//' comment (to end of line). This should be used to place
#      command specific comments.
#
#  08) Command abbreviation support has been added. It is denoted in the first
#      field as follows:
#        <cmdroot>[<cmdstem-letter-set>]   - concat letters to root as a
#                                            every growing substring
#        <cmdroot>[<suffix1>|<suffix2>...] - concat supplied suffixes to root
#
#       e.g. "ver[sion]"   describes the set {"ver", "vers", "versi", "versio"
#            "ver[s|sion]" describes the set {"vers", "version"}
#            "ver[|sion]"  describes the set {"ver", "version"} NOTE: The
#                          suffix set consists of "", and "sion".
#
# Each command takes one line. Lines that start with the character # are comments. Comments are for
# adding notes and description and will be ignored by the command parser.
