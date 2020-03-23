import os

import pytest
import torch

import deepsmlm.generic.emitter as emitter
from deepsmlm.generic.emitter import EmitterSet, RandomEmitterSet, EmptyEmitterSet
from deepsmlm.generic.utils import test_utils


class TestEmitterSet:

    @pytest.fixture()
    def em2d(self):
        """
        Fixture 2D EmitterSet.

        Returns:
            EmitterSet

        """
        return EmitterSet(xyz=torch.rand((25, 2)),
                          phot=torch.rand(25),
                          frame_ix=torch.zeros(25).int())

    @pytest.fixture()
    def em3d(self):
        """
        3D EmitterSet.
        Returns:
            EmitterSet
        """
        frames = torch.arange(25)
        frames[[0, 1, 2]] = 1
        return EmitterSet(xyz=torch.rand((25, 3)),
                          phot=torch.rand(25),
                          frame_ix=frames)

    def test_xyz_shape(self, em2d, em3d):
        """
        Tests shape and correct data type
        Args:
            em2d: fixture (see above)
            em3d: fixture (see above)

        Returns:

        """

        # 2D input get's converted to 3D with zeros
        assert em2d.xyz.shape[1] == 3
        assert em3d.xyz.shape[1] == 3

        assert em3d.frame_ix.dtype in (torch.int, torch.long, torch.short)

    xyz_conversion_data = [  # xyz_input, # xy_unit, #px-size # expect px, # expect nm
        (torch.empty((0, 3)), None, None, "err", "err"),
        (torch.empty((0, 3)), 'px', None, torch.empty((0, 3)), "err"),
        (torch.empty((0, 3)), 'nm', None, "err", torch.empty((0, 3))),
        (torch.tensor([[25., 25., 5.]]), None, None, "err", "err"),
        (torch.tensor([[25., 25., 5.]]), 'px', None, torch.tensor([[25., 25., 5.]]), "err"),
        (torch.tensor([[25., 25., 5.]]), 'nm', None, "err", torch.tensor([[25., 25., 5.]])),
        (torch.tensor([[.25, .25, 5.]]), 'px', (50., 100.), torch.tensor([[.25, .25, 5.]]), torch.tensor([[12.5, 25., 5.]])),
        (torch.tensor([[25., 25., 5.]]), 'nm', (50., 100.), torch.tensor([[.5, .25, 5.]]), torch.tensor([[25., 25., 5.]]))
    ]

    @pytest.mark.parametrize("xyz_input,xy_unit,px_size,expct_px,expct_nm", xyz_conversion_data)
    @pytest.mark.filterwarnings("ignore:UserWarning")
    def test_xyz_conversion(self, xyz_input, xy_unit, px_size, expct_px, expct_nm):

        """Init and expect warning if specified"""
        em = emitter.CoordinateOnlyEmitter(xyz_input, xy_unit=xy_unit, px_size=px_size)

        """Test the respective units"""
        if isinstance(expct_px, str) and expct_px == "err":
            with pytest.raises(ValueError):
                _ = em.xyz_px
        else:
            assert test_utils.tens_almeq(em.xyz_px, expct_px)

        if isinstance(expct_nm, str) and expct_nm == "err":
            with pytest.raises(ValueError):
                _ = em.xyz_nm

        else:
            assert test_utils.tens_almeq(em.xyz_nm, expct_nm)

    @pytest.mark.parametrize("xyz_cr_input,xy_unit,px_size,expct_px,expct_nm", xyz_conversion_data)
    @pytest.mark.filterwarnings("ignore:UserWarning")
    def test_xyz_cr_conversion(self, xyz_cr_input, xy_unit, px_size, expct_px, expct_nm):
        """
        Here we test the cramer rao unit conversion. We can reuse the testdata as for the xyz conversion because it does
        not make a difference for the test candidate.

        """

        """Init and expect warning if specified"""
        em = emitter.CoordinateOnlyEmitter(torch.rand_like(xyz_cr_input), xy_unit=xy_unit, px_size=px_size)
        em.xyz_cr = xyz_cr_input

        """Test the respective units"""
        if isinstance(expct_px, str) and expct_px == "err":
            with pytest.raises(ValueError):
                _ = em.xyz_cr_px
        else:
            assert test_utils.tens_almeq(em.xyz_cr_px, expct_px)

        if isinstance(expct_nm, str) and expct_nm == "err":
            with pytest.raises(ValueError):
                _ = em.xyz_cr_nm

        else:
            assert test_utils.tens_almeq(em.xyz_cr_nm, expct_nm)

    def test_split_in_frames(self, em2d, em3d):
        splits = em2d.split_in_frames(None, None)
        assert splits.__len__() == 1

        splits = em3d.split_in_frames(None, None)
        assert em3d.frame_ix.max() - em3d.frame_ix.min() + 1 == len(splits)

        """Test negative numbers in Frame ix."""
        neg_frames = EmitterSet(torch.rand((3, 3)),
                                torch.rand(3),
                                torch.tensor([-1, 0, 1]))
        splits = neg_frames.split_in_frames(None, None)
        assert splits.__len__() == 3
        splits = neg_frames.split_in_frames(0, None)
        assert splits.__len__() == 2

    def test_adjacent_frame_split(self):
        xyz = torch.rand((500, 3))
        phot = torch.rand_like(xyz[:, 0])
        frame_ix = torch.randint_like(xyz[:, 0], low=-1, high=2).int()
        em = EmitterSet(xyz, phot, frame_ix)

        em_split = em.split_in_frames(-1, 1)
        assert (em_split[0].frame_ix == -1).all()
        assert (em_split[1].frame_ix == 0).all()
        assert (em_split[2].frame_ix == 1).all()

        em_split = em.split_in_frames(0, 0)
        assert em_split.__len__() == 1
        assert (em_split[0].frame_ix == 0).all()

        em_split = em.split_in_frames(-1, -1)
        assert em_split.__len__() == 1
        assert (em_split[0].frame_ix == -1).all()

        em_split = em.split_in_frames(1, 1)
        assert em_split.__len__() == 1
        assert (em_split[0].frame_ix == 1).all()

    def test_cat_emittersets(self):
        """
        Test the concatenation of two emittersets.
        :return:
        """
        sets = [RandomEmitterSet(50), RandomEmitterSet(20)]
        cat_sets = EmitterSet.cat(sets, None, 1)
        assert 70 == len(cat_sets)
        assert 0 == cat_sets.frame_ix[0]
        assert 1 == cat_sets.frame_ix[50]

        sets = [RandomEmitterSet(50), RandomEmitterSet(20)]
        cat_sets = EmitterSet.cat(sets, torch.tensor([5, 50]), None)
        assert 70 == len(cat_sets)
        assert 5 == cat_sets.frame_ix[0]
        assert 50 == cat_sets.frame_ix[50]

    def test_sanity_check(self):
        """Test correct shape of 1D tensors in EmitterSet"""
        xyz = torch.rand((10, 3))
        phot = torch.rand((10, 1))
        frame_ix = torch.rand(10)
        with pytest.raises(ValueError):
            EmitterSet(xyz, phot, frame_ix)

        """Test correct number of el. in EmitterSet."""
        xyz = torch.rand((10, 3))
        phot = torch.rand((11, 1))
        frame_ix = torch.rand(10)
        with pytest.raises(ValueError):
            EmitterSet(xyz, phot, frame_ix)

    @pytest.mark.skip("Function deprecated and will be moved.")
    def test_write_to_csv(self):
        """
        Test to write to csv file.
        :return:
        """
        deepsmlm_root = os.path.abspath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         os.pardir, os.pardir)) + '/'

        random_em = RandomEmitterSet(1000)
        fname = deepsmlm_root + 'deepsmlm/test/assets/dummy_csv.txt'
        random_em.write_to_csv(fname)
        assert os.path.isfile(fname)
        os.remove(fname)

    @pytest.mark.skip("Function deprecated and will be moved.")
    def test_write_to_SMAP(self):
        deepsmlm_root = os.path.abspath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         os.pardir, os.pardir)) + '/'

        random_em = RandomEmitterSet(1000, 6400)
        random_em.px_size = torch.tensor([100., 100.])
        random_em.xy_unit = 'nm'
        fname = deepsmlm_root + 'deepsmlm/test/assets/dummy_csv.txt'
        random_em.write_to_csv_format(fname, lud_name='challenge')
        assert os.path.isfile(fname)
        os.remove(fname)

    def test_eq(self):
        em = RandomEmitterSet(1000)
        em2 = em.clone()

        assert em == em2


def test_empty_emitterset():
    em = EmptyEmitterSet()
    assert 0 == len(em)


class TestLooseEmitterSet:

    @pytest.fixture(scope='class')
    def dummy_set(self):
        num_emitters = 10000
        t0_max = 5000
        em = emitter.LooseEmitterSet(torch.rand((num_emitters, 3)), torch.ones(num_emitters) * 10000,
                                     torch.rand(num_emitters) * 3, torch.rand(num_emitters) * t0_max, None,
                                     xy_unit='px')

        return em

    def test_distribution(self):
        loose_em = emitter.LooseEmitterSet(torch.zeros((2, 3)), torch.tensor([1000., 10]), torch.tensor([1., 5]),
                                           torch.tensor([-0.2, 0.9]), None,
                                           xy_unit='px')

        em = loose_em.return_emitterset()
