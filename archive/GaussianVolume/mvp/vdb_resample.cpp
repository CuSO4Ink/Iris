// Minimal OpenVDB fog-volume resampler used for reproducible A/B assets.
#include <openvdb/io/File.h>
#include <openvdb/openvdb.h>
#include <openvdb/tools/GridTransformer.h>

#include <cstdlib>
#include <iostream>
#include <string>

int main(int argc, char** argv)
{
    if (argc != 4) {
        std::cerr << "usage: vdb_resample <input.vdb> <output.vdb> <linear-factor>\n";
        return 2;
    }
    const double factor = std::strtod(argv[3], nullptr);
    if (!(factor > 0.0)) {
        std::cerr << "linear-factor must be positive\n";
        return 2;
    }

    openvdb::initialize();
    openvdb::io::File input(argv[1]);
    input.open();
    auto source = openvdb::gridPtrCast<openvdb::FloatGrid>(input.readGrid("density"));
    input.close();
    if (!source) {
        std::cerr << "float grid named density not found\n";
        return 1;
    }

    auto output = openvdb::FloatGrid::create(source->background());
    output->setName(source->getName());
    output->setGridClass(source->getGridClass());
    output->setTransform(openvdb::math::Transform::createLinearTransform(
        source->voxelSize().x() * factor));
    openvdb::tools::resampleToMatch<openvdb::tools::BoxSampler>(*source, *output);
    output->tree().prune();

    openvdb::GridPtrVec grids{output};
    openvdb::io::File result(argv[2]);
    result.write(grids);
    result.close();

    const auto bounds = output->evalActiveVoxelBoundingBox();
    const auto dimensions = bounds.dim();
    std::cout << "active_voxels=" << output->activeVoxelCount()
              << " dimensions=" << dimensions.x() << 'x' << dimensions.y() << 'x' << dimensions.z()
              << " voxel_size=" << output->voxelSize().x() << '\n';
    return 0;
}
