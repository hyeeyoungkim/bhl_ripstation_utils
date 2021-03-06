import argparse
import csv
import os
import re
import subprocess

parser = argparse.ArgumentParser(description='Make A/V DIPs from the RipStation (AKA Jackie).')
parser.add_argument('-i', '--input', required=True, help='Input directory')
parser.add_argument('-o', '--output', required=True, help='Output directory')
args = parser.parse_args()


# Function
def get_target(src_path, dst_path):
    temp_list = []
    return_list = []
    with open(os.path.join(src_path, 'bhl_inventory.csv'), mode='r') as bhl_inventory_csv_file:
        csv_reader = csv.DictReader(bhl_inventory_csv_file)
        csv_reader.fieldnames = [fieldname.strip().lower() for fieldname in csv_reader.fieldnames]

        # Removing non-targets, rows that are not audio CD or video DVD
        for row in csv_reader:
            if row['media_type'] == 'audio CD' or row['media_type'] == 'video DVD':
                temp_list.append(dict(row))

        # Removing non-targets, rows that are separation and have DIP made using this script
        for row in temp_list:
            if row['separation'] == 'Y':
                temp_list.remove(row)

            if row['media_type'] == 'audio CD':
                if os.path.isfile(os.path.join(dst_path, row['barcode'] + '.wav')) is True:
                    temp_list.remove(row)

            if row['media_type'] == 'video DVD':
                if os.path.isfile(os.path.join(dst_path, row['barcode'] + '.mp4')) is True:
                    temp_list.remove(row)

        # Adding targets, rows that are successful and have no DIP made
        for row in temp_list:
            if row['pass_1_successful'] == 'Y' and row['made_dip'] != 'Y':
                barcode_and_media_type = [row['barcode'], row['media_type']]
                return_list.append(barcode_and_media_type)

            if row['pass_1_successful'] == 'N' and row['pass_2_successful'] == 'Y' and row['made_dip'] != 'Y':
                barcode_and_media_type = [row['barcode'], row['media_type']]
                return_list.append(barcode_and_media_type)

        return return_list


# Forked from Max's script
def mk_wav(src, barcode, dst):
    print('Making .WAV for barcode ' + barcode)

    # writing temporary input text file
    tracks = [name for name in os.listdir(os.path.join(src, barcode)) if name.endswith('.wav')]
    with open(os.path.join(src, barcode, 'mylist.txt'), mode='w') as f:
        for track in sorted(tracks):
            f.write("file '" + os.path.join(src, barcode, track) + "'\n")

    # concatenating
    cmd = [
        os.path.join('ffmpeg', 'bin', 'ffmpeg.exe'),
        '-f', 'concat',
        '-safe', '0',
        '-i', os.path.join(src, barcode, 'mylist.txt'),
        '-c', 'copy',
        os.path.join(dst, barcode + '.wav')
    ]
    exit_code = subprocess.call(cmd)

    # deleting temporary input text file
    os.remove(os.path.join(src, barcode, 'mylist.txt'))

    result_list.append([barcode, exit_code])


# Forked from Max's script
def mk_mp4(src, barcode, dst):
    for name in os.listdir(os.path.join(src, barcode)):
        if os.path.splitext(name)[1].startswith('.iso'):

            # get title count
            cmd = [
                os.path.join('HandBrakeCLI', 'HandBrakeCLI.exe'),
                '-i', os.path.join(src, barcode, name),
                '-t', '0'
            ]
            # https://www.saltycrane.com/blog/2008/09/how-get-stdout-and-stderr-using-python-subprocess-module/
            p = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
            output = p.stdout.read().decode('ISO-8859-1')  # utf-8
            match = re.findall('scan: DVD has (\d+) title\(s\)', output)

            title_count = 1

            if match:
                title_count = int(match[0])

            # make mp4 for single-title DVD
            if title_count == 1:
                print('\nMaking .MP4 for ' + barcode)

                cmd = [
                    os.path.join('HandBrakeCLI', 'HandBrakeCLI.exe'),
                    '-Z', 'High Profile',
                    '-i', os.path.join(src, barcode, name),
                    '-o', os.path.join(dst, os.path.splitext(name)[0] + '.mp4')
                ]
                exit_code = subprocess.call(cmd)

                result_list.append([barcode, exit_code])

            # make mp4 for each title in multi-title DVD
            else:
                count = 1

                while count <= title_count:
                    print('\nMaking .MP4 for title ' + str(count) + ' of ' + str(title_count))

                    cmd = [
                        os.path.join('HandBrakeCLI', 'HandBrakeCLI.exe'),
                        '--title', str(count),
                        '-Z', 'High Profile',
                        '-i', os.path.join(src, barcode, name),
                        '-o', os.path.join(dst, os.path.splitext(name)[0] + '-' + str(count) + '.mp4')
                    ]
                    exit_code = subprocess.call(cmd)
                    result_list.append([barcode + '-' + str(count), exit_code])

                    count += 1


# Script
target_list = get_target(args.input, args.output)
result_list = []

for target in target_list:
    if target[1] == 'audio CD':
        mk_wav(args.input, target[0], args.output)

    if target[1] == 'video DVD':
        mk_mp4(args.input, target[0], args.output)

for result in result_list:
    if result[1] == 0:
        print(result[0], 'success with exit code', + result[1])

    else:
        print(result[0], 'fail with exit code', + result[1])
