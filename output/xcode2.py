# Xcode 2.0 generation by David F. Elliott
#
# $Id$

# NOTE: This needs a lot of work yet, but it's a good start

import re

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
        self.nextObjectId = 0
    def getNextObjectId(self):
        objectID = self.nextObjectId
        self.nextObjectId += 1
        return XcodeObjectId(objectID)

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

def serializeDictionary(dict, level):
    stringList = []
    stringList.append("{\n")
    dictKeys = dict.keys()
    dictKeys.sort()
    for key in dictKeys:
        for x in range(0,level+1):
            stringList.append("\t")
        stringList.append(serializeAnything(key,level+1))
        stringList.append(" = ")
        stringList.append(serializeAnything(dict[key],level+1))
        stringList.append(";\n")
    for x in range(0,level):
        stringList.append("\t")
    stringList.append("}")
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
        
        ###################################################################
        # Create the root object (PBXProject instance)
        self.theRootObject = {}
        self.theRootObject["isa"] = "PBXProject"
        self.theRootObject["buildSettings"] = {} #Can be empty
        self.theRootObject["buildStyles"] = [] #TODO Release vs. Debug, we probably need at least a dummy one.
        self.theRootObject["hasScannedForEncodings"] = 1 # TODO: ?
#        self.theRootObject["mainGroup"] = someObject (done later)
#        self.theRootObject["productRefGroup"] = someObject (done later)
        self.theRootObject["projectDirPath"] = "" #TODO: ?
        self.theRootObject["targets"] = [] # Fill with targets

        # Make an ID for the root object and add it to objects
        rootObjectID = self.objectIdGenerator.getNextObjectId()
        self.rootObject = rootObjectID
        self.objects[rootObjectID] = self.theRootObject


        ###################################################################
        # Now make the Main Group (PBXGroup)
        self.theMainGroup = {}
        self.theMainGroup["isa"] = "PBXGroup"
        self.theMainGroup["children"] = []
        self.theMainGroup["name"] = self.basename
        self.theMainGroup["refType"] = 4;
        self.theMainGroup["sourceTree"] = "<group>";

        # Assign an ID
        mainGroupID = self.objectIdGenerator.getNextObjectId()
        # Set it as the mainGroup on the project instance
        self.theRootObject["mainGroup"] = mainGroupID
        # Add it to objects
        self.objects[mainGroupID] = self.theMainGroup


        ###################################################################
        # Now make the Product Ref group (PBXGroup)
        self.theProductRefGroup = {}
        self.theProductRefGroup["isa"] = "PBXGroup"
        self.theProductRefGroup["children"] = []
        self.theProductRefGroup["name"] = "Products"
        self.theProductRefGroup["refType"] = 4
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
        # Now go through the targets and configs of targets
        for t in self.targets:
            for cKey in t.configs:
                config = t.configs[cKey]
                if config._kind == "binary_product":
                    self.genBinaryTarget(t,cKey,config)

        pbxprojDict = {}
        pbxprojDict["archiveVersion"] = 1
        pbxprojDict["classes"] = []
        pbxprojDict["objectVersion"] = 39
        pbxprojDict["objects"] = self.objects
        pbxprojDict["rootObject"] = self.rootObject

        pbxprojData = "// !$*UTF8*$!\n"
        pbxprojData += serializeDictionary(pbxprojDict,0)
#        pbxprojData += "{\n"
#
#        pbxprojData += "\tobjects = "
#        pbxprojData += serializeDictionary(self.objects,1)
#        pbxprojData += ";\n"
#
#        pbxprojData += "}"

        #TODO: Check if FILE (foo.xcode) is a directory and make it if necessary
        if not os.path.isdir(self.xcodeProjectDirname):
            os.mkdir(self.xcodeProjectDirname)
        writer.writeFile(self.pbxprojFilename, pbxprojData)


    def idForDirectoryGroup(self, path):
        if self.directoryGroups.has_key(path):
            return self.directoryGroups[path]
        dirname, basename = os.path.split(path)
        groupID = self.objectIdGenerator.getNextObjectId()
#        print "Creating new group=%s for path=%s" % (groupID, path)
        groupObject = {}
        groupObject["isa"] = "PBXGroup"
        groupObject["sourceTree"] = "<group>"
        groupObject["children"] = []
        parentGroupObject = None
        if dirname == None or dirname == "":
            parentGroupObject = self.theMainGroup
            groupObject["refType"] = 2 # Relative to project
            # FIXME: assuming project in something like build/xcode
            groupObject["path"] = os.path.join("../..",basename)
            groupObject["name"] = basename
        else:
            parentGroupObject = self.objects[self.idForDirectoryGroup(dirname)]
            groupObject["refType"] = 4 # Relative to enclosing group
            groupObject["path"] = basename

#        print "Group %s =" % groupID, groupObject
        self.objects[groupID] = groupObject
        parentGroupObject["children"].append(groupID)
        self.directoryGroups[path] = groupID
        return groupID

    def idForSourceFile(self, path):
        if self.sourceFiles.has_key(path):
            return self.sourceFiles[path]
        dirname, basename = os.path.split(path)
        groupId = self.idForDirectoryGroup(dirname)
        fileId = self.objectIdGenerator.getNextObjectId()
        fileObject = {}
        fileObject["isa"] = "PBXFileReference"
        fileObject["path"] = basename
        fileObject["refType"] = 4 # Path relative to enclosing group

        self.objects[fileId] = fileObject
#        print "Adding file to group=%s" % groupId
        self.objects[groupId]["children"].append(fileId)
        self.sourceFiles[path] = fileId
        return fileId

    def genBinaryTarget(self, target, configName, config):
        # 1. Create target
        # 2. Create build phase
        # 3. Add files to build phase
        print "%s - %s" % (target._targetname, configName)
        print config._productname

        ###################################################################
        # Create the target object
        targetObject = {}
        targetObject["isa"] = "PBXNativeTarget"
        targetObject["buildPhases"] = [] # Create build phase (see below)
        targetObject["buildRules"] = [] # (normally empty)
        targetObject["buildSettings"] = {} # Fill with env vars
        targetObject["dependencies"] = []
        targetObject["name"] = "%s - %s" % (target._targetname, configName)
#        targetObject["productName"] = None # Often same as name, sometimes not, is it needed?
#        targetObject["productReference"] = None # See below
        targetObject["productType"] = config._productType
        targetId = self.objectIdGenerator.getNextObjectId()
        self.objects[targetId] = targetObject
        self.theRootObject["targets"].append(targetId)


        ###################################################################
        # Create the product reference object (references lib*.a or whatever)
        productObject = {}
        productObject["isa"] = "PBXFileReference"
        productObject["explicitFileType"] = config._explicitFileType
        productObject["includeInIndex"] = 0
        productObject["path"] = config._productname # why do two __ not work?
        productObject["refType"] = 3
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
        for sourceFile in config._sources.split():
            # Add as a file ref (if it isn't already)
            # The ref ids are per project basically
            fileRefId = self.idForSourceFile(sourceFile)
            # Now create a build file object
            buildFile = {}
            buildFile["isa"] = "PBXBuildFile"
            buildFile["settings"] = {}
            buildFile["fileRef"] = fileRefId
            buildFileId = self.objectIdGenerator.getNextObjectId()
            self.objects[buildFileId] = buildFile
            compileBuildPhase["files"].append(buildFileId)

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
