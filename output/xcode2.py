#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2005-2007 David F. Elliott, Kevin Ollivier
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to
#  deal in the Software without restriction, including without limitation the
#  rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
#  sell copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
#  IN THE SOFTWARE.
#
#  $Id$
#
#  Xcode 2.4 generation
#

# NOTE: This needs a lot of work yet, but it's a good start

import re

XCODE_BAKEFILE_NAMESPACE = "{3dfbab82-f4ee-11db-abee-0013d4abf640}"

def mk_uuid(namespace, seed):
    # NB: we want to have the GUID strings be repeatable so, generate them
    #     from a repeatable seed
    from uuid import uuid5, UUID

    guid = uuid5(UUID(namespace), seed)
    return '%s' % str(guid).upper() # MSVS uses upper-case strings for GUIDs

class XcodeObjectId:
    def __init__(self, integer):
        self.integer = integer
    def __str__(self):
        return "%024x" % self.integer
    def __cmp__(self, other):
        return self.integer - other.integer
    def __hash__(self):
        return self.integer

class ObjectIdGenerator:
    def __init__(self):
        self.nextObjectId = 1
    def getNextObjectId(self):
        objectID = self.nextObjectId
        self.nextObjectId += 1
        return XcodeObjectId(objectID)

def mk_xcode_uuid(seed):
    thisuuid = mk_uuid(XCODE_BAKEFILE_NAMESPACE, seed)
    return thisuuid

safeStringCharsRegex = re.compile("^[A-Za-z0-9_./][A-Za-z0-9_./]*$")
# NOTE: it is ALWAYS safe to quote string values.  Xcode will have
# no trouble reading it.  It just looks ugly.

def serializeString(string):
    # Empty strings MUST be empty quotes
    if string == "":
        return "\"\""
    # TODO: is this right?
    if safeStringCharsRegex.match(string):
        return string
    return "\"%s\"" % string

def serializeInteger(integer):
    return str(integer)

def serializeAnything(something, level):
    t = type(something)
    if t == int:
        return serializeInteger(something)
    elif t == str:
        return serializeString(something)
    elif t == dict:
        return serializeDictionary(something,level)
    elif t == list:
        return serializeList(something, level)
    else:
        try:
            return something.__str__()
        except:
            return "PLEASE IMPLEMENT FOR %s" % t;

def serializeList(list, level):
    ret = "(\n"
    for value in list:
        for x in range(0,level+1):
            ret += "\t"
        ret += serializeAnything(value,level+1)
        ret += ",\n"
    for x in range(0,level):
        ret += "\t"
    ret += ")"
    return ret
    
def sortDictByIsaProp(dict):
    """ 
    Xcode projects sort the top-level output objects by their 'isa' key, 
    so we should do the same to enable easier comparison of original and 
    Bakefile Xcode projects. Note that this is mostly a debugging tool,
    and if it gives problems later on we should just remove it.
    """
    isadict = {}
    for key in dict.keys():
        if dict[key].has_key("isa"):
            isa = dict[key]["isa"]
            if not isadict.has_key(isa):
                isadict[isa] = []
            isadict[isa].append(key)
    keys = isadict.keys()
    keys.sort()
    values = []
    for key in keys:
        for item in isadict[key]:
            values.append(item)
    return values

def serializeDictionary(dict, level):
    stringList = []
    stringList.append("{\n")
    if level == 1:
        dictKeys = sortDictByIsaProp(dict)
    else:
        dictKeys = dict.keys()
        dictKeys.sort()
    
    lastIsa = ""
    
    # While Xcode normally sorts keys alphabetically, it makes an exception
    # for the 'isa' key, which it always lists first. We will try to duplicate 
    # this in order to make projects output more similar project files.
    try:
        dictKeys.remove("isa")
        dictKeys.insert(0, "isa")
    except:
        pass 
        
    for key in dictKeys:
        
        # The native Xcode project format puts in begin/end section comments,
        # which really make it easier to read through the file, so I went ahead
        # and added this capability to  Bakefile too.
        if hasattr(dict[key], "has_key") and dict[key].has_key("isa"):
            isa = dict[key]["isa"]
            if isa != lastIsa:
                if lastIsa != "":
                    stringList.append("/* End %s section */\n" % lastIsa) 
                stringList.append("\n/* Begin %s section */\n" % isa)
            lastIsa = isa
        
        for x in range(0,level+1):
            stringList.append("\t")
        stringList.append(serializeAnything(key,level+1))
        stringList.append(" = ")
        stringList.append(serializeAnything(dict[key],level+1))
        stringList.append(";\n")
    for x in range(0,level):
        stringList.append("\t")
    stringList.append("}")
    if lastIsa != "":
        stringList.append("\n/* End %s section */\n\n" % lastIsa) 

    return "".join(stringList)
    
#refType
#   0   Absolute
#   1   ?Unused?
#   2   Relative to Project (where foo.xcode is)
#   3   Relative to build product
#   4   Relative to Enclosing group
class ProjectGeneratorXcode2:
    def __init__(self, _targets, targetGroupName=""):
        self.targets = _targets
        self.basename, self.extension = os.path.splitext(os.path.basename(FILE))
        if targetGroupName != "":
            self.basename += "_" + targetGroupName
        self.dirname = os.path.dirname(FILE)
        self.xcodeProjectDirname = os.path.join(self.dirname,self.basename + self.extension)
        self.pbxprojFilename = os.path.join(self.xcodeProjectDirname, "project.pbxproj")
        self.objectIdGenerator = ObjectIdGenerator()

    def genProject(self):
#        self.dumpVars()

        # objects is the flat store of all PBX* serialized objects
        # It is a dictionary indexed by object ID.
        # Gets written to the project.pbxproj file.
        self.objects = {}
        # sourceFiles is a dictionary which stores the object ID for
        # a given source file path.  Makes it easy to see if we've
        # added the file to the project yet
        # An object with an ID in this dictionary will be a PBXFileReference.
        self.sourceFiles = {}
        # DirectoryGroups does the same thing for directories.
        # An object with an ID in this dictionary will be a PBXGroup.
        self.directoryGroups = {}
        # Xcode maps dependencies using IDs, so it is very helpful to have a
        # bakefile ID -> Xcode ID mapping when setting up dependencies.
        self.targetIds = {}
        
        
        ###################################################################
        # Create the root object (PBXProject instance)
        self.theRootObject = {}
        self.theRootObject["isa"] = "PBXProject"
        self.theRootObject["hasScannedForEncodings"] = 1 # TODO: ?
#        self.theRootObject["mainGroup"] = someObject (done later)
#        self.theRootObject["productRefGroup"] = someObject (done later)
        self.theRootObject["projectDirPath"] = "" #TODO: ?
        self.theRootObject["targets"] = [] # Fill with targets

        # Make an ID for the root object and add it to objects
        rootObjectID = mk_xcode_uuid(self.basename + "_project")
        self.rootObject = rootObjectID
        self.objects[rootObjectID] = self.theRootObject


        ###################################################################
        # Now make the Main Group (PBXGroup)
        self.theMainGroup = {}
        self.theMainGroup["isa"] = "PBXGroup"
        self.theMainGroup["children"] = []
        self.theMainGroup["name"] = self.basename
        #self.theMainGroup["refType"] = 4;
        self.theMainGroup["sourceTree"] = "<group>";

        # We need to create a project configuration that is the same name as the
        # 'default' config, otherwise Xcode will create a config for us but name it
        # "Development" and also default to that configuration.       
        projectConfigIds = []
        for config in configs:
            buildConfig = {}
            buildConfig["isa"] = "XCBuildConfiguration"
            buildConfig["name"] = config
            buildConfig["buildSettings"] = {}
    
            buildConfigId = self.objectIdGenerator.getNextObjectId()
            self.objects[buildConfigId] = buildConfig
            projectConfigIds.append(buildConfigId)
            
        projectConfigList = {}
        projectConfigList["isa"] = "XCConfigurationList"
        projectConfigList["defaultConfigurationIsVisible"] = 0
        projectConfigList["defaultConfigurationName"] = configs.keys()[-1]
        projectConfigList["buildConfigurations"] = projectConfigIds
        
        projectConfigListId = self.objectIdGenerator.getNextObjectId()
        self.objects[projectConfigListId] = projectConfigList
        self.theRootObject["buildConfigurationList"] = projectConfigListId
        
        # Assign an ID
        self.mainGroupId = self.objectIdGenerator.getNextObjectId()
        # Set it as the mainGroup on the project instance
        self.theRootObject["mainGroup"] = self.mainGroupId
        # Add it to objects
        self.objects[self.mainGroupId] = self.theMainGroup


        ###################################################################
        # Now make the Product Ref group (PBXGroup)
        self.theProductRefGroup = {}
        self.theProductRefGroup["isa"] = "PBXGroup"
        self.theProductRefGroup["children"] = []
        self.theProductRefGroup["name"] = "Products"
        #self.theProductRefGroup["refType"] = 4
        self.theProductRefGroup["sourceTree"] = "<group>"

        # Assign an ID
        productRefGroupID = self.objectIdGenerator.getNextObjectId()
        # Set it as the productRefGroup on the project instance
        self.theRootObject["productRefGroup"] = productRefGroupID
        # Make it a child of the main group
        self.theMainGroup["children"].append(productRefGroupID)
        # Add it to objects
        self.objects[productRefGroupID] = self.theProductRefGroup


        ###################################################################
        # Now go through the targets
        for t in self.targets:
            if t._kind == "binary_product":
                self.genBinaryTarget(t)
            elif t._kind == "action":
                self.genShellScriptBuildPhase(t._targetname, t._commands)

        pbxprojDict = {}
        pbxprojDict["archiveVersion"] = 1
        pbxprojDict["classes"] = {}
        pbxprojDict["objectVersion"] = 42 # == Xcode 2.4?
        pbxprojDict["objects"] = self.objects
        pbxprojDict["rootObject"] = self.rootObject

        pbxprojData = "// !$*UTF8*$!\n"
        pbxprojData += serializeDictionary(pbxprojDict,0)

        #TODO: Check if FILE (foo.xcode) is a directory and make it if necessary
        writer.Mkdir(self.xcodeProjectDirname)
        writer.writeFile(self.pbxprojFilename, pbxprojData)

    def idForDirectoryGroup(self, dirname):
        if self.directoryGroups.has_key(dirname):
            return self.directoryGroups[dirname]
        # TODO: Check this further - isn't this a bug if the basename
        parentdir = os.path.split(dirname)[0]
        groupID = self.objectIdGenerator.getNextObjectId()
        print "Creating new group=%s for path=%s" % (groupID, dirname)
        groupObject = {}
        groupObject["isa"] = "PBXGroup"
        groupObject["sourceTree"] = "<group>"
        groupObject["children"] = []
        parentGroupObject = self.objects[self.mainGroupId]
        
        # NB: Ideally, it'd be nice to have a directory hierarchy like the below
        # code attempts to do, but it is not robust enough to handle multiple
        # subdirs, and moreover, I'm not sure how relative dirs will be resolved 
        # using nested file groups, so for the moment don't create a dir hierarchy.
        
        #if parentdir != "":
        #    parentGroupObject = self.objects[self.idForDirectoryGroup(parentdir)]
        #groupObject["refType"] = 4 # Relative to enclosing group
        groupObject["path"] = dirname
        
        # name is just for when you want to use logical groups (e.g. "Bakefiles")
        # rather than showing the files in a path. Since Bakefile doesn't yet have
        # a cross-format 'logical' grouping of source files, we don't need to set
        # the 'name' property for now.
        #groupObject["name"] = basename

#        print "Group %s =" % groupID, groupObject
        self.objects[groupID] = groupObject
        parentGroupObject["children"].append(groupID)
        self.directoryGroups[dirname] = groupID
        return groupID

    def idForSourceFile(self, path):
        if self.sourceFiles.has_key(path):
            return self.sourceFiles[path]
        dirname, basename = os.path.split(path)
        # At least in projects I looked at, source files in the root dir of the
        # project used the main group's ID.
        if dirname == "":
            groupId = self.mainGroupId 
        else:
            groupId = self.idForDirectoryGroup(dirname)
            
        fileId = self.objectIdGenerator.getNextObjectId()
        fileObject = {}
        fileObject["isa"] = "PBXFileReference"
        fileObject["path"] = basename
        fileObject["sourceTree"] = "<group>";
        #fileObject["refType"] = 4 # Path relative to enclosing group

        self.objects[fileId] = fileObject
#        print "Adding file to group=%s" % groupId
        self.objects[groupId]["children"].append(fileId)
        self.sourceFiles[path] = fileId
        return fileId

    def getBuildConfigs(self, target):
        configIds = []
        for configName in target.configs:
            config = target.configs[configName]
            buildSettings = {}
            
            #includes 
            buildSettings["PRODUCT_NAME"] = config._productname
            if config._includes != "":
                buildSettings["USER_HEADER_SEARCH_PATHS"] = config._includes
                
            if config._lib_path != "":
                    buildSettings["LIBRARY_SEARCH_PATHS"] = config._lib_path
            
            if config._defines != "":
                buildSettings["GCC_PREPROCESSOR_DEFINITIONS"] = config._defines
            
            # map on/off in Bakefile to YES/NO in Xcode
            off_on_dict = {"off" : "NO", "on": "YES"}
            
            if config._cxx_rtti != "":
                buildSettings["GCC_ENABLE_CPP_RTTI"] = off_on_dict[config._cxx_rtti]
                
            if config._cxx_exceptions == "off":
                buildSettings["GCC_ENABLE_CPP_EXCEPTIONS"] = off_on_dict[config._cxx_exceptions]
    
            if config._debug_info != "":
                buildSettings["GCC_GENERATE_DEBUGGING_SYMBOLS"] = off_on_dict[config._debug_info]
                
            if config._optimize != "":
                opt_settings = {"off": "0", "speed": "2", "size": "s"}
                buildSettings["GCC_OPTIMIZATION_LEVEL"] = opt_settings[config._optimize]
    
            if config._cflags != "":
                buildSettings["OTHER_CFLAGS"] = config._cflags
                
            if config._cppflags != "":
                buildSettings["OTHER_CPLUSPLUSFLAGS"] = config._cppflags
                
            if config._dirname != "":
                buildSettings["SYMROOT"] = config._dirname
                buildSettings["CONFIGURATION_BUILD_DIR"] = config._dirname
            
            # currently we don't do anything with 'no' or 'default' values, like GNU format
            if config._warnings == "max":
                buildSettings["WARNING_CFLAGS"] = "-W -Wall"
            
            buildSettings["OTHER_LDFLAGS"] = ""
            if config._ldflags != "":
                buildSettings["OTHER_LDFLAGS"] += config._ldflags
                
            if config._ldlibs != "":
                buildSettings["OTHER_LDFLAGS"] += " " + config._ldlibs
                
            if config._use_pch != "":
                buildSettings["GCC_PRECOMPILE_PREFIX_HEADER"] = off_on_dict[config._use_pch]
                
            if config._pch_header != "":
                buildSettings["GCC_PREFIX_HEADER"] = config._pch_header
                
            # NB! The Bakefile setting asks whether PIC should be used, whereas the Xcode
            # setting asks whether it should NOT be used. So we need to set it to the 
            # opposite of the Bakefile value.  
            if config._pic != "":
                usepic = "on"
                if config._pic == "on":
                    usepic = "off"
                buildSettings["GCC_DYNAMIC_NO_PIC"] = off_on_dict[usepic]
                
            if target._macvercur != "":
                buildSettings["DYLIB_CURRENT_VERSION"] = target._macvercur
                
            if target._macvercompat != "":
                buildSettings["DYLIB_COMPATIBILITY_VERSION"] = target._macvercompat
    
            buildConfig = {}
            buildConfig["isa"] = "XCBuildConfiguration"
            buildConfig["name"] = configName        
            buildConfig["buildSettings"] = buildSettings
    
            buildConfigId = self.objectIdGenerator.getNextObjectId()
            self.objects[buildConfigId] = buildConfig
            configIds.append(buildConfigId)

        return configIds
        
    def getOrCreateTargetId(self, targetName):
        """
        We may need to create a target ID at two different times:
        - when creating a new target
        - when adding the target as a dependency to another
        This function will create the target ID if needed, otherwise
        it will return the existing value.
        """
        if not self.targetIds.has_key(targetName):
            self.targetIds[targetName] = self.objectIdGenerator.getNextObjectId()
        
        return self.targetIds[targetName]

    def generateDependencies(self, target):
        deplist = []
        
        # NB: You may notice after looking over this code that it will create
        # duplicate objects if a target is a dependency of two or more other
        # targets. This is how Xcode does it, and I think we should match the 
        # behavior even if it's less efficient than reusing dependency objects.
        for dep in target._deps.split(" "):
            # we create a build phase for an action target, which we handle 
            # separately
            if dep != "" and not self.targets[dep]._kind == "action":
                proxyObj = {}
                proxyObj["isa"] = "PBXContainerItemProxy"
                proxyObj["proxyType"] = 1 # not sure what this is...
                proxyObj["containerPortal"] = self.rootObject
                proxyObj["remoteGlobalIDString"] = self.getOrCreateTargetId(dep)
                proxyObj["remoteInfo"] = dep
                
                proxyObjId = self.objectIdGenerator.getNextObjectId()
                self.objects[proxyObjId] = proxyObj
                
                targetDep = {}
                targetDep["isa"] = "PBXTargetDependency"
                targetDep["target"] = self.getOrCreateTargetId(dep)
                targetDep["targetProxy"] = proxyObjId
                
                targetObjId = self.objectIdGenerator.getNextObjectId()
                self.objects[targetObjId] = targetDep
                deplist.append(targetObjId)
            
        return deplist

    def genShellScriptBuildPhase(self, name, script):
        buildPhase = {}
        buildPhase["isa"] = "PBXShellScriptBuildPhase"
        buildPhase["buildActionMask"] = 2147483647 # not sure what this is...
        buildPhase["files"] = []
        buildPhase["inputPaths"] = []
        buildPhase["outputPaths"] = []
        buildPhase["runOnlyForDeploymentPostprocessing"] = 0
        buildPhase["shellPath"] = "/bin/sh" # TODO: default used by Xcode, is this appropriate here?
        buildPhase["shellScript"] = script # target._commands
        
        buildPhaseId = self.getOrCreateTargetId(name)
        self.objects[buildPhaseId] = buildPhase

    def genBinaryTarget(self, target):
        # 1. Create target
        # 2. Create build phase
        # 3. Add files to build phase
        print "%s" % (target._targetname)

        ###################################################################
        # Create the target object
        targetObject = {}
        targetObject["isa"] = "PBXNativeTarget"
        targetObject["buildPhases"] = [] # Create build phase (see below)
        targetObject["buildRules"] = [] # (normally empty)
        targetObject["dependencies"] = self.generateDependencies(target)
        targetObject["name"] = target._targetname
        #targetObject["productName"] = targetObject["name"] #is this needed?
        targetObject["productType"] = target._productType
        targetId = self.getOrCreateTargetId(target._targetname)
        self.objects[targetId] = targetObject
        self.theRootObject["targets"].append(targetId)

        ###################################################################
        # Create the configuration(s) for the target
            
        configList = {}
        configList["isa"] = "XCConfigurationList"
        configList["defaultConfigurationIsVisible"] = 0
        configList["defaultConfigurationName"] = target.configs.keys()[-1]
        configList["buildConfigurations"] = self.getBuildConfigs(target)
        
        configListId = self.objectIdGenerator.getNextObjectId()
        self.objects[configListId] = configList
        targetObject["buildConfigurationList"] = configListId

        ###################################################################
        # Create the product reference object (references lib*.a or whatever)
        productObject = {}
        productObject["isa"] = "PBXFileReference"
        productObject["lastKnownFileType"] = target._explicitFileType
        productObject["includeInIndex"] = 0
        productObject["path"] = target._targetname
        #productObject["refType"] = 3
        productObject["sourceTree"] = "BUILT_PRODUCTS_DIR"

        productId = self.objectIdGenerator.getNextObjectId()
        self.objects[productId] = productObject
        targetObject["productReference"] = productId
        self.theProductRefGroup["children"].append(productId)

        ###################################################################
        # Create the build phase to compile source files
        compileBuildPhase = {}
        compileBuildPhase["isa"] = "PBXSourcesBuildPhase"
        compileBuildPhase["buildActionMask"] = 2147483647 #WTF is this?
        compileBuildPhase["files"] = []
        compileBuildPhase["runOnlyForDeploymentPostprocessing"] = 0

        compileBuildPhaseId = self.objectIdGenerator.getNextObjectId()
        self.objects[compileBuildPhaseId] = compileBuildPhase
        targetObject["buildPhases"].append(compileBuildPhaseId)

        ###################################################################
        # Now run through the source files
        for sourceFile in target._sources.split():
            # Add as a file ref (if it isn't already)
            # The ref ids are per project basically
            fileRefId = self.idForSourceFile(sourceFile)
            # Now create a build file object
            buildFile = {}
            buildFile["isa"] = "PBXBuildFile"
            # buildFile["settings"] = {}
            buildFile["fileRef"] = fileRefId
            buildFileId = self.objectIdGenerator.getNextObjectId()
            self.objects[buildFileId] = buildFile
            compileBuildPhase["files"].append(buildFileId)
            
        mydeps = target._deps.split(" ")
        for dep in mydeps:
            if dep != "" and self.targets[dep]._kind == "action":
                # Since actions are dependencies, we should insert them before the
                # other build phases.
                targetObject["buildPhases"].insert(0, self.getOrCreateTargetId(dep))
        
        self.generateDependencies(target)
        
        if target._postlink_command != "":
            phaseName = target._targetname + "_postlink_command"
            self.genShellScriptBuildPhase(phaseName, target._postlink_command)
            targetObject["buildPhases"].append(self.getOrCreateTargetId(phaseName))

    def dumpVars(self):
#        for c in configs_order:
#            print c
#        for c in configs:
#            print c
        for t in self.targets:
            print "id=",t._targetname
#            print "sources=",t._sources.split()
#            print "COMPILER=", COMPILER
#            print "CONFIGS=",t.configs
            print
            for cKey in t.configs:
                config = t.configs[cKey]
                print "config=%s - %s" % (t._targetname,cKey)
                print "config._kind=%s" % config._kind
                if config._kind == "binary_product":
                    print "t.configs[c]._sources=",config._sources
                print
            print

class Struct:
    pass

def run():
    print FILE
    targetGroups = {}
    targetGroups[""] = Struct()
    targetGroups[""].targets = writer.Container()
    for t in targets:
        # All non-binary targets immediately go to basename.xcode
        if t._kind != "binary_product":
            targetGroups[""].targets.append(t.id,t)
        else:
            for cKey in t.configs:
                config = t.configs[cKey]
                groupname = config._xcode_target_group
                # If we haven't created the target group yet, do so
                if not targetGroups.has_key(groupname):
                    targetGroups[groupname] = Struct()
                    targetGroups[groupname].targets = writer.Container()
                # If the target group doesn't have this target in it, add it
                if not targetGroups[groupname].targets.dict.has_key(t.id):
                    groupedTarget = Struct()
                    # copy all variables except for configs
                    for varname in vars(t):
                        if varname != "configs":
                            setattr(groupedTarget, varname, getattr(t, varname))
                    # Create an empty configs dictoinary
                    groupedTarget.configs = {}
                    targetGroups[groupname].targets.append(groupedTarget.id, groupedTarget)

                # Add this config to the grouped target
                targetGroups[groupname].targets[t.id].configs[cKey] = config

    targetGroupKeys = targetGroups.keys()
    targetGroupKeys.sort()
    for targetGroupKey in targetGroupKeys:
        targetGroup = targetGroups[targetGroupKey]
        print "--- GENERATING %s PROJECT ---" % targetGroupKey
        generator = ProjectGeneratorXcode2(targetGroup.targets, targetGroupKey)
        generator.genProject()
