# It is important to note that this script will include your PTH components as well as your SMT components.
# You will need to later select which parts are skipped or not.
# Copyright 2018 Michael Moskie
# mod 2020 to Python3
import sys
from decimal import Decimal
import argparse


class Component:
    # just a structure to represent a physical component
    def __init__(self, line):
        # "Designator","Comment","Layer","Footprint","Center-X(mm)","Center-Y(mm)","Rotation","Description"
        self.Designator = line.split(',')[0]
        self.Footprint = (str(line.split(',')[3]).replace("\"", ""))
        self.Layer = (str(line.split(',')[2]).replace("\"", ""))
        self.X = line.split(',')[4].replace("\"", "")
        self.Y = line.split(',')[5].replace("\"", "")
        self.Layer = line.split(',')[2].replace("\"", "")
        self.Rotation = line.split(',')[6].replace("\"", "")
        self.Comment = line.split(',')[1].replace("\"", "")
        self.nozzle = 0
        self.feeder = 0
        self.skip = 'No'


class CorrectionForElement:
    def __init__(self, footprint, correction):
        self.Footprint = footprint
        self.Correction = correction


class Part:
    def __init__(self, footprint, comment, part='', feeder=0, nozzle=0):
        self.Footprint = footprint
        self.Comment = comment
        self.feeder = feeder
        self.nozzle = nozzle
        self.part = part
        self.quantity = 1


class NeoDenConverter:
    def make_component_list(self):
        counter = 0
        for line in self.AltiumOutputFile:
            if counter < 13:
                # throw away the header.
                pass
            else:
                new_element = Component(line)
                self.components.append(new_element)
                self.footprints.add(new_element.Footprint)

            counter += 1

    def get_distances_from_first_chip(self):
        first_chip_x = 0
        first_chip_y = 0
        counter = 0
        for comp in self.components:
            if counter == 0:
                # this is the first component
                first_chip_x = comp.X
                first_chip_y = comp.Y
                comp.X = 0
                comp.Y = 0
            else:
                comp.X = float(comp.X) - float(first_chip_x)
                comp.Y = float(comp.Y) - float(first_chip_y)
            counter += 1

    def apply_machine_positions_2_components(self):
        for comp in self.components:
            comp.X += self.firstChipPhysicalX
            comp.Y += self.firstChipPhysicalY

    def __feeder_n_nozzle_str__(self, component):
        if self.feeders_data_flag:
            str_preamble = "comp," + str(component.feeder) + ", " + str(component.nozzle) + ", "
        else:
            part = component.Footprint + "/" + component.Comment
            str_preamble = "comp," + "FEEDER_4_" + part + ",NOZZLE_4_" + part + "," + ", "
        return str_preamble

    def create_output_file(self, layer):
        output_file = open(self.AltiumOutputFile.name.replace(".csv", "-NEODEN.csv"), "w")

        output_file.write("# Mirror,First component X,First component Y,Rotation,Skip,\n" +
                        "mirror, " + str(self.components[0].X) + ", " + str(self.components[0].Y) + ", " +
                        str(self.components[0].Rotation) + ", No,\n\n")
        output_file.write("#Chip,Feeder ID,Nozzle,Name,Value,Footprint,X,Y,Rotation,Skip\n")
        for comp in self.components:
            if not layer or comp.Layer == layer:
                out_line = self.__feeder_n_nozzle_str__(comp) +\
                           str(comp.Designator).replace("\"", "") + "," + \
                           comp.Comment + "," + str(comp.Footprint).replace("\"", "") + "," + \
                           str(round(Decimal(comp.X), 2)) + "," + str(round(Decimal(comp.Y), 2)) + "," + \
                           str(comp.Rotation).replace("\"", "") + "," + comp.skip + ","
                output_file.write(out_line + "\n")

    def create_footprints_file(self):
        output_file = open(self.AltiumOutputFile.name.replace(".csv", "-FOOTPRINTS.csv"), "w")
        output_file.write("#Footprint,RotationCorrection\n")
        for f in self.footprints:
            output_file.write(str(f) + ",0.00\n")
        output_file.close()
        return output_file.name

    def create_parts_set(self):
        for component in self.components:
            part = component.Footprint + '/' + component.Comment
            if not (part in self.parts_names):
                self.parts_names.add(part)
                self.parts.append(Part(component.Footprint, component.Comment, part))
            else:
                for p in self.parts:
                    if part == p.part:
                        p.quantity += 1
                        break
        print("parts:" + str(len(self.parts))+"\n")

    def create_parts_file(self):
        output_file = open(self.AltiumOutputFile.name.replace(".csv", "-PARTS.csv"), "w")
        output_file.write("#Use find-n-replace tool in text editor for config feeders, unconfigurated will marked as 'Skip:Yes'\n")
        output_file.write("#Part,Feeder,Nozzle,qnt,Field 4 your comment c\n")
        for part in self.parts:
            output_file.write(part.Footprint + '\\' + part.Comment + ",0,0," + str(part.quantity) + ",\n")
        output_file.close()

    def make_angles_correction(self, correction_file_name):
        try:
            corr_file = open(correction_file_name, "r")
        except FileNotFoundError:
            print("No such correction file\n")
            return FileNotFoundError
        counter = 0
        for line in corr_file:
            if counter:
                footprint = line.split(',')[0]
                corr = line.split(',')[1]
                self.corrections.append(CorrectionForElement(str(footprint), float(corr)))
            counter += 1
        corrected = set()
        for component in self.components:
            for correction in self.corrections:
                if component.Footprint == correction.Footprint and correction.Correction != 0:
                    component.Rotation = str(float(correction.Correction) + float(component.Rotation))
                    corrected.add(component.Footprint)
                    break
        print("angles corrected for: ")
        print(corrected)
        return 0

    def add_feeders(self, feeders_file_name):
        try:
            feeders_file = open(feeders_file_name, "r")
        except FileNotFoundError:
            print("No such feeders file\n")
            return FileNotFoundError
        feeders_confs = list()
        self.feeders_data_flag = True
        for line in feeders_file:
            if line[0] != '#':
                part = line.split(',')[0]
                feeder = int(line.split(',')[1])
                nozzle = int(line.split(',')[2])
                feeders_confs.append(Part(None, None, feeder=feeder, nozzle=nozzle, part=part))
        for component in self.components:
            part_str = component.Footprint + '\\' + component.Comment
            component.skip = 'Yes'
            for conf in feeders_confs:
                if part_str == conf.part:
                    if conf.feeder and conf.nozzle:
                        component.feeder = conf.feeder
                        component.nozzle = conf.nozzle
                        component.skip = 'No'
                    else:
                        component.feeder = self.default_feeder
                        component.nozzle = self.default_nozzle
        return 0

    def move_angels_to_m180to180(self):
        for component in self.components:
            while float(component.Rotation) > 180.00:
                component.Rotation = str(float(component.Rotation) - 360.00)
            while float(component.Rotation) < -180.00:
                component.Rotation = str(float(component.Rotation) + 360.00)

    def flip_board(self):
        for comp in self.components:
            comp.X = str(float(comp.X) * (-1))
            comp.Rotation = str(360.00 - float(comp.Correction))

    def __init__(self, file_name):
        try:
            self.AltiumOutputFile = open(file_name, "r")
        except FileNotFoundError:
            print("No such file\n")
            exit(-1)
        self.footprints = set()
        self.components = list()
        self.parts_names = set()
        self.parts = list()
        self.corrections = list()
        self.make_component_list()
        self.feeders_data_flag = False
        self.default_feeder = 80
        self.default_nozzle = 1
        self.flip_flag = False
        self.firstChipPhysicalX = 0.0
        self.firstChipPhysicalY = 0.0
        return


description = "Program for creating .CSV files for Neoden3V"
file_help = '*.csv file from Altium'
fp_help = "generate footprints list for making angle correction between Altium libs and position in tapes"
cl_help = "generate components list for convenient pairing components and feeders"
cf_help = "correct footprints rotation from file CF"
feed_help = "include components and feeders pairs from file PC"
top_help = "filter only top layer components"
bot_help = "filter only bot layer components"
flip_help = "flip board"


def create_parser():
    arg_parser = argparse.ArgumentParser(description=description)
    arg_parser.add_argument('FILE', type=str, help=file_help)
    arg_parser.add_argument('-fp', action=argparse.BooleanOptionalAction, type=bool, default=False, help=fp_help)
    arg_parser.add_argument('-cl', action=argparse.BooleanOptionalAction, type=bool, default=False, help=cl_help)
    arg_parser.add_argument('-top', action=argparse.BooleanOptionalAction, type=bool, default=False, help=top_help)
    arg_parser.add_argument('-bot', action=argparse.BooleanOptionalAction, type=bool, default=False, help=bot_help)
    arg_parser.add_argument('-flip', action=argparse.BooleanOptionalAction, type=bool, default=False, help=flip_help)
    arg_parser.add_argument('-cf', type=str, help=cf_help)
    arg_parser.add_argument('-feed', type=str, help=feed_help)
    return arg_parser


argc = len(sys.argv)
parser = create_parser()
args = parser.parse_args(sys.argv[1:])
print(args)

print("*****************")

converter = NeoDenConverter(args.FILE)
no_output_generate_flag = False

if args.fp:
    frame = converter.create_footprints_file()
    print("template of footprints angle correction file is generated(" + frame + ")\n")
    no_output_generate_flag = True
if args.cl:
    converter.create_parts_set()
    converter.create_parts_file()
    no_output_generate_flag = True

if args.cf:
    if 0 == converter.make_angles_correction(args.cf):
        print("successful correction\n")
    else:
        exit(0)

if args.feed:
    if 0 == converter.add_feeders(args.feed):
        print("successful feeders config\n")
    else:
        exit(0)

if no_output_generate_flag:
    exit(0)

if args.top:
    layer_flag = 'TopLayer'
else:
    if args.bot:
        layer_flag = 'BottomLayer'
    else:
        layer_flag = None

if args.flip:
    converter.flip_board()


converter.move_angels_to_m180to180()
converter.get_distances_from_first_chip()
converter.firstChipPhysicalX = float(
    input("Enter the machine X coordinate of component " + converter.components[0].Designator + " : "))
converter.firstChipPhysicalY = float(
    input("Enter the machine Y coordinate of component " + converter.components[0].Designator + " : "))
converter.apply_machine_positions_2_components()
converter.create_output_file(layer_flag)
